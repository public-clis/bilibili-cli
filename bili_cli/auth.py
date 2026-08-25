"""Authentication for Bilibili.

Strategy:
1. Try loading saved credential from ~/.bilibili-cli/credential.json
2. Try extracting cookies from local browsers via browser-cookie3
3. Fallback: QR code login via bilibili-api-python + terminal display
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, unquote, urlparse

import qrcode
from bilibili_api.utils.network import Credential

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".bilibili-cli"
CREDENTIAL_FILE = CONFIG_DIR / "credential.json"

# Required cookies for a valid Bilibili session
REQUIRED_COOKIES = {"SESSDATA"}

# Extra cookie fields that help bypass Bilibili's 412 anti-scraping checks
EXTRA_COOKIE_FIELDS = ("buvid3", "buvid4", "dedeuserid")

# Credential TTL: warn and attempt refresh after 7 days
CREDENTIAL_TTL_DAYS = 7
_CREDENTIAL_TTL_SECONDS = CREDENTIAL_TTL_DAYS * 86400


AuthMode = Literal["optional", "read", "write"]


def get_credential(mode: AuthMode = "read") -> Credential | None:
    """Try auth methods in order and return credential according to mode.

    - optional: only load saved credential (no network validation, no browser scan)
    - read: prefer validated credential; if validation is indeterminate (network),
      return saved/browser credential as best effort
    - write: same as read, but require bili_jct capability
    """
    require_write = mode == "write"

    # 1. Saved credential file
    cred = _load_saved_credential()
    if cred:
        # Check TTL — try to refresh from browser if stale
        if _is_credential_stale():
            logger.info("Credential older than %d days, attempting browser refresh", CREDENTIAL_TTL_DAYS)
            fresh = _extract_browser_credential()
            if fresh:
                validation = _validate_credential(fresh, require_write=require_write)
                if validation is True:
                    logger.info("Refreshed credential from browser")
                    save_credential(fresh)
                    return fresh
            # Refresh failed — validate existing credential
            logger.warning(
                "Credential is %d+ days old; browser refresh failed. Validating existing credential...",
                CREDENTIAL_TTL_DAYS,
            )

        if mode == "optional":
            return cred
        validation = _validate_credential(cred, require_write=require_write)
        if validation is True:
            logger.info("Loaded valid credential from %s", CREDENTIAL_FILE)
            return cred
        if validation is None:
            logger.warning("Credential validation failed due to network; using saved credential as best effort")
            return cred
        if validation is False:
            logger.warning("Saved credential is expired, clearing")
            clear_credential()

    if mode == "optional":
        return None

    # 2. Browser cookie extraction
    cred = _extract_browser_credential()
    if cred:
        validation = _validate_credential(cred, require_write=require_write)
        if validation is True:
            logger.info("Extracted valid credential from local browser")
            save_credential(cred)
            return cred
        if validation is None:
            logger.warning("Skipping browser credential validation due to network; using best effort")
            return cred
        if validation is False:
            logger.warning("Browser cookies are expired/invalid")

    return None


def _is_credential_stale() -> bool:
    """Check if saved credential file is older than TTL."""
    if not CREDENTIAL_FILE.exists():
        return False
    try:
        data = json.loads(CREDENTIAL_FILE.read_text())
        saved_at = data.get("saved_at", 0)
        if not saved_at:
            # Legacy file without saved_at — treat as stale to add the field
            return True
        return (time.time() - saved_at) > _CREDENTIAL_TTL_SECONDS
    except (json.JSONDecodeError, OSError):
        return False


def _validate_credential(cred: Credential, require_write: bool = False) -> bool | None:
    """Check if a credential is valid.

    Returns:
      - True: credential validated by API
      - False: credential confirmed invalid or missing required fields
      - None: validation is indeterminate due to network/runtime issues
    """
    from bilibili_api import user
    from bilibili_api.exceptions import NetworkException

    if not getattr(cred, "sessdata", ""):
        return False
    if require_write and not getattr(cred, "bili_jct", ""):
        return False

    async def _check():
        try:
            await user.get_self_info(cred)
            return True
        except NetworkException:
            return None
        except Exception:
            return False

    try:
        return asyncio.run(_check())
    except Exception:
        return None


def _load_saved_credential() -> Credential | None:
    """Load credential from saved file."""
    if not CREDENTIAL_FILE.exists():
        return None

    try:
        data = json.loads(CREDENTIAL_FILE.read_text())
        sessdata = data.get("sessdata", "")
        if not sessdata:
            return None
        return Credential(
            sessdata=sessdata,
            bili_jct=data.get("bili_jct", ""),
            ac_time_value=data.get("ac_time_value", ""),
            buvid3=data.get("buvid3", ""),
            buvid4=data.get("buvid4", ""),
            dedeuserid=data.get("dedeuserid", ""),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to load saved credential: %s", e)
        return None


def _extract_browser_credential() -> Credential | None:
    """Extract Bilibili cookies from local browsers using browser-cookie3.

    Runs extraction in a subprocess with timeout to avoid hanging
    when the browser is running (Chrome DB lock issue).
    """
    extract_script = '''
import json, sys
try:
    import browser_cookie3 as bc3
except ImportError:
    print(json.dumps({"error": "not_installed"}))
    sys.exit(0)

browsers = [
    ("Chrome", bc3.chrome),
    ("Firefox", bc3.firefox),
    ("Edge", bc3.edge),
    ("Brave", bc3.brave),
]

for name, loader in browsers:
    try:
        cj = loader(domain_name=".bilibili.com")
        cookies = {c.name: c.value for c in cj if "bilibili.com" in (c.domain or "")}
        if "SESSDATA" in cookies:
            print(json.dumps({"browser": name, "cookies": cookies}))
            sys.exit(0)
    except Exception:
        pass

print(json.dumps({"error": "no_cookies"}))
'''

    try:
        result = subprocess.run(
            [sys.executable, "-c", extract_script],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            logger.debug("Cookie extraction subprocess failed: %s", result.stderr)
            return None

        output = result.stdout.strip()
        if not output:
            logger.debug("Cookie extraction returned empty output")
            return None

        data = json.loads(output)

        if "error" in data:
            if data["error"] == "not_installed":
                logger.debug("browser-cookie3 not installed, skipping")
            else:
                logger.debug("No valid Bilibili cookies found in any browser")
            return None

        cookies = data["cookies"]
        browser_name = data["browser"]
        if not REQUIRED_COOKIES.issubset(cookies):
            logger.debug("Browser cookies missing required keys: %s", REQUIRED_COOKIES)
            return None
        logger.info(
            "Found valid cookies in %s (%d cookies)", browser_name, len(cookies)
        )

        return Credential(
            sessdata=cookies.get("SESSDATA", ""),
            bili_jct=cookies.get("bili_jct", ""),
            ac_time_value=cookies.get("ac_time_value", ""),
            buvid3=cookies.get("buvid3", ""),
            buvid4=cookies.get("buvid4", ""),
            dedeuserid=cookies.get("DedeUserID", ""),
        )

    except subprocess.TimeoutExpired:
        logger.warning(
            "Cookie extraction timed out (browser may be running). "
            "Try closing your browser or use `bili login`."
        )
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Cookie extraction parse error: %s", e)
        return None


def save_credential(credential: Credential):
    """Save credential to config file with timestamp for TTL tracking."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "sessdata": credential.sessdata,
        "bili_jct": credential.bili_jct,
        "ac_time_value": credential.ac_time_value or "",
        "buvid3": credential.buvid3 or "",
        "buvid4": credential.buvid4 or "",
        "dedeuserid": credential.dedeuserid or "",
        "saved_at": time.time(),
    }
    CREDENTIAL_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    CREDENTIAL_FILE.chmod(0o600)  # Owner-only read/write
    logger.info("Credential saved to %s", CREDENTIAL_FILE)


def clear_credential():
    """Remove saved credential file."""
    if CREDENTIAL_FILE.exists():
        CREDENTIAL_FILE.unlink()
        logger.info("Credential removed: %s", CREDENTIAL_FILE)


def _supports_unicode_half_blocks() -> bool:
    """Return True when stdout encoding can represent half-block glyphs."""
    encoding = getattr(sys.stdout, "encoding", None)
    if not encoding:
        return False
    try:
        "▀▄█".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _render_compact_qr(data: str) -> str | None:
    """Render a compact QR code using Unicode half-block characters.

    Uses ▀, ▄, █, and space to encode two vertical modules per character row,
    reducing the QR code height by half compared to full-block rendering.
    Each module is 1 character wide (vs 2 in qrcode-terminal), so total area
    is ~25% of the original.
    """
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    # Add 1-module quiet zone
    size = len(matrix)
    padded = [[False] * (size + 2)]
    for row in matrix:
        padded.append([False] + list(row) + [False])
    padded.append([False] * (size + 2))
    matrix = padded
    rows = len(matrix)

    # Check terminal width and warn if too narrow
    term_cols = shutil.get_terminal_size(fallback=(80, 24)).columns
    qr_width = len(matrix[0])
    if qr_width > term_cols:
        logger.warning(
            "Terminal width (%d) too narrow for compact QR (%d), falling back",
            term_cols,
            qr_width,
        )
        return None

    lines: list[str] = []
    # Process two rows at a time using half-block characters
    # top=black, bottom=black → █ (full block)
    # top=black, bottom=white → ▀ (upper half)
    # top=white, bottom=black → ▄ (lower half)
    # top=white, bottom=white → ' ' (space)
    for y in range(0, rows, 2):
        line = ""
        top_row = matrix[y]
        bottom_row = matrix[y + 1] if y + 1 < rows else [False] * len(top_row)
        for x in range(len(top_row)):
            top = top_row[x]
            bottom = bottom_row[x]
            if top and bottom:
                line += "█"
            elif top and not bottom:
                line += "▀"
            elif not top and bottom:
                line += "▄"
            else:
                line += " "
        lines.append(line)
    return "\n".join(lines)


def _get_qr_terminal_output(login: Any) -> str:
    """Choose compact QR rendering when possible, otherwise use default output."""
    default_qr = login.get_qrcode_terminal()

    qr_link = getattr(login, "_QrCodeLogin__qr_link", None)
    if not qr_link:
        logger.warning("QR link unavailable from QrCodeLogin internals, using default renderer")
        return default_qr

    if not _supports_unicode_half_blocks():
        logger.warning("stdout encoding cannot render Unicode QR blocks, using default renderer")
        return default_qr

    compact_qr = _render_compact_qr(qr_link)
    if compact_qr is None:
        return default_qr
    return compact_qr


QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
_QR_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _parse_set_cookie_headers(headers) -> dict[str, str]:
    """Extract name/value pairs from raw Set-Cookie header values."""
    cookies: dict[str, str] = {}
    # aiohttp / multidict may expose getall; fallback to single get
    if hasattr(headers, "getall"):
        items = headers.getall("Set-Cookie", [])
    else:
        raw = headers.get("Set-Cookie")
        items = [raw] if raw else []
    for item in items:
        head = item.split(";", 1)[0]
        if "=" not in head:
            continue
        name, value = head.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def _cookies_from_login_url(url: str) -> dict[str, str]:
    """Parse legacy crossDomain URLs that embed SESSDATA in the query string."""
    qs = parse_qs(urlparse(url).query)
    out: dict[str, str] = {}
    for key in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"):
        if key in qs and qs[key]:
            out[key] = unquote(qs[key][0])
    return out


def _credential_from_cookie_map(cookies: dict[str, str], refresh_token: str = "") -> Credential | None:
    sessdata = cookies.get("SESSDATA", "")
    if not sessdata:
        return None
    return Credential(
        sessdata=unquote(sessdata),
        bili_jct=cookies.get("bili_jct", ""),
        dedeuserid=cookies.get("DedeUserID", cookies.get("dedeuserid", "")),
        ac_time_value=refresh_token or cookies.get("refresh_token", "") or "",
        buvid3=cookies.get("buvid3", ""),
        buvid4=cookies.get("buvid4", ""),
    )


async def _follow_login_url_for_cookies(session, url: str) -> dict[str, str]:
    """Follow ticket/crossDomain URL and collect any Set-Cookie values."""
    cookies: dict[str, str] = {}
    if not url:
        return cookies
    try:
        async with session.get(url, allow_redirects=True) as resp:
            cookies.update(_parse_set_cookie_headers(resp.headers))
            for cookie in session.cookie_jar:
                if cookie.key not in cookies and cookie.value:
                    cookies[cookie.key] = cookie.value
    except Exception as exc:  # pragma: no cover - network best effort
        logger.debug("Follow login URL failed: %s", exc)
    return cookies


async def qr_login() -> Credential:
    """QR code login via terminal (web channel).

    Displays a QR code in the terminal, polls until login completes,
    then saves and returns the credential.

    Bilibili's web poll may return a ticket/cross-domain URL whose query
    string no longer contains SESSDATA. The real cookies are delivered via
    ``Set-Cookie`` on the poll response (and sometimes via following the
    login URL). Capture those headers instead of relying on bilibili-api's
    URL-only parser, which can save an empty credential file.
    """
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=30)
    jar = aiohttp.CookieJar(unsafe=True)
    headers = {"User-Agent": _QR_UA, "Referer": "https://www.bilibili.com/"}

    async with aiohttp.ClientSession(cookie_jar=jar, timeout=timeout, headers=headers) as session:
        async with session.get(QR_GENERATE_URL) as resp:
            payload = await resp.json(content_type=None)
        if payload.get("code") != 0:
            raise RuntimeError(f"生成二维码失败: {payload.get('message') or payload}")
        data = payload.get("data") or {}
        qr_link = data.get("url") or ""
        qrcode_key = data.get("qrcode_key") or ""
        if not qr_link or not qrcode_key:
            raise RuntimeError("生成二维码失败: 响应缺少 url 或 qrcode_key")

        class _QrLink:
            def __init__(self, link: str):
                self._QrCodeLogin__qr_link = link

            def get_qrcode_terminal(self) -> str:
                compact = _render_compact_qr(self._QrCodeLogin__qr_link)
                if compact:
                    return compact
                return self._QrCodeLogin__qr_link

        print("\n📱 请使用 Bilibili App 扫描以下二维码登录:\n")
        print(_get_qr_terminal_output(_QrLink(qr_link)))
        print("\n⭐ 扫码后请在手机上确认登录...")

        confirmed = False
        while True:
            async with session.get(QR_POLL_URL, params={"qrcode_key": qrcode_key}) as resp:
                body = await resp.json(content_type=None)
                set_cookies = _parse_set_cookie_headers(resp.headers)
                for cookie in session.cookie_jar:
                    if cookie.key not in set_cookies and cookie.value:
                        set_cookies[cookie.key] = cookie.value

            data = body.get("data") or {}
            status = int(data.get("code", -1))

            if status == 0 and data.get("url"):
                cookies = dict(set_cookies)
                cookies.update(_cookies_from_login_url(data["url"]))
                if "SESSDATA" not in cookies:
                    cookies.update(await _follow_login_url_for_cookies(session, data["url"]))

                credential = _credential_from_cookie_map(
                    cookies, refresh_token=data.get("refresh_token") or ""
                )
                if credential is None:
                    raise RuntimeError(
                        "登录完成但未拿到有效 SESSDATA，请重试 `bili login`"
                    )
                credential = await _enrich_credential_buvids(credential)
                save_credential(credential)
                print("\n✅ 登录成功！凭证已保存")
                return credential

            if status == 86038:
                raise RuntimeError("二维码已过期，请重试")

            if status == 86090 and not confirmed:
                print("  📲 已扫码，请在手机上确认...")
                confirmed = True

            await asyncio.sleep(2)


async def _enrich_credential_buvids(credential: Credential) -> Credential:
    """Best-effort fill buvid3/buvid4 to reduce HTTP 412 wind-control hits."""
    if getattr(credential, "buvid3", "") and getattr(credential, "buvid4", ""):
        return credential
    try:
        from bilibili_api.utils.network import get_buvid

        buvid3, buvid4 = await get_buvid()
    except Exception as exc:  # pragma: no cover - network best effort
        logger.debug("Skipping buvid enrichment: %s", exc)
        return credential

    return Credential(
        sessdata=credential.sessdata,
        bili_jct=credential.bili_jct,
        ac_time_value=credential.ac_time_value or "",
        buvid3=getattr(credential, "buvid3", "") or buvid3 or "",
        buvid4=getattr(credential, "buvid4", "") or buvid4 or "",
        dedeuserid=getattr(credential, "dedeuserid", "") or "",
    )
