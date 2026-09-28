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
from typing import Literal

import qrcode
from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents
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
    extract_script = """
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
"""

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
        logger.info("Found valid cookies in %s (%d cookies)", browser_name, len(cookies))

        return Credential(
            sessdata=cookies.get("SESSDATA", ""),
            bili_jct=cookies.get("bili_jct", ""),
            ac_time_value=cookies.get("ac_time_value", ""),
            buvid3=cookies.get("buvid3", ""),
            buvid4=cookies.get("buvid4", ""),
            dedeuserid=cookies.get("DedeUserID", ""),
        )

    except subprocess.TimeoutExpired:
        logger.warning("Cookie extraction timed out (browser may be running). Try closing your browser or use `bili login`.")
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


def _get_qr_terminal_output(login: QrCodeLogin) -> str:
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


async def _fetch_crossdomain_cookies(cred_url: str) -> dict[str, str]:
    """Follow a Bilibili QR-login crossDomain ticket URL and collect cookies
    from the ``Set-Cookie`` response headers.

    Since 2026-08 Bilibili returns a crossDomain ticket link (without cookies)
    as the login success URL; the real ``SESSDATA`` / ``bili_jct`` /
    ``DedeUserID`` cookies are delivered via ``Set-Cookie`` headers when
    following that link with a browser User-Agent.
    """
    import aiohttp

    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
        "Referer": "https://passport.bilibili.com/",
    }
    cookies: dict[str, str] = {}
    async with aiohttp.ClientSession() as session:
        async with session.get(cred_url, headers=headers, allow_redirects=False) as resp:
            for raw in resp.headers.getall("Set-Cookie", []):
                pair = raw.split(";", 1)[0]
                if "=" not in pair:
                    continue
                name, value = pair.split("=", 1)
                cookies[name.strip()] = value
    return cookies


def _build_credential_from_cookies(cookies: dict[str, str], ac_time_value: str = "") -> Credential:
    """Build a Credential from raw cookie values."""
    return Credential(
        sessdata=cookies.get("SESSDATA", ""),
        bili_jct=cookies.get("bili_jct", ""),
        ac_time_value=ac_time_value or cookies.get("ac_time_value", ""),
        buvid3=cookies.get("buvid3", ""),
        buvid4=cookies.get("buvid4", ""),
        dedeuserid=cookies.get("DedeUserID", ""),
    )


def _parse_qr_events(events: dict) -> QrCodeLoginEvents:
    """Map WEB QR-poll event codes to QrCodeLoginEvents."""
    code = events.get("code")
    if code == 86101:
        return QrCodeLoginEvents.SCAN
    if code == 86090:
        return QrCodeLoginEvents.CONF
    if code == 86038:
        return QrCodeLoginEvents.TIMEOUT
    return QrCodeLoginEvents.DONE


async def _patched_check_state(self: QrCodeLogin) -> QrCodeLoginEvents:
    """Drop-in replacement for bilibili-api's ``QrCodeLogin.check_state`` that
    handles Bilibili's 2026+ crossDomain QR-login response format.

    Since 2026-08 the WEB QR-login success response no longer embeds cookies in
    the ``url`` query string: ``data.url`` is a crossDomain ticket link and the
    real ``SESSDATA`` / ``bili_jct`` / ``DedeUserID`` cookies arrive via
    ``Set-Cookie`` headers when following it.  bilibili-api's own ``login_v2``
    (<=17.4.2) only parses cookies from the URL, so it yields an empty
    ``sessdata``.  We reimplement WEB polling here so the credential is
    captured at the moment the login completes (re-polling later is not
    possible: the ``qrcode_key`` is invalidated once the login succeeds).

    Installed via ``QrCodeLogin.check_state = _patched_check_state`` below.
    """
    from bilibili_api.utils.network import Api
    from bilibili_api.utils.utils import get_api

    qr_key = getattr(self, "_QrCodeLogin__qr_key", "")
    if not qr_key:
        raise RuntimeError("QR code has not been generated yet")

    api = get_api("login")["qrcode"]["web"]["get_events"]
    events = await Api(credential=Credential(), **api).update_params(qrcode_key=qr_key).result
    events = events or {}

    state = _parse_qr_events(events)
    if state != QrCodeLoginEvents.DONE:
        return state

    # Login succeeded: build the credential ourselves.
    cred_url = events.get("url", "")
    ac_time_value = events.get("refresh_token", "")
    if "SESSDATA=" in cred_url:
        # Legacy format: cookies embedded in the URL query string.
        sessdata = bili_jct = dedeuserid = ""
        for cookie in cred_url.split("?")[1].split("&"):
            if cookie[:8] == "SESSDATA":
                sessdata = cookie[9:]
            elif cookie[:8] == "bili_jct":
                bili_jct = cookie[9:]
            elif cookie[:11].upper() == "DEDEUSERID=":
                dedeuserid = cookie[11:]
        credential = Credential(
            sessdata=sessdata,
            bili_jct=bili_jct,
            dedeuserid=dedeuserid,
            ac_time_value=ac_time_value,
        )
    elif cred_url:
        # New format: crossDomain ticket link; cookies via Set-Cookie headers.
        cookies = await _fetch_crossdomain_cookies(cred_url)
        if not cookies.get("SESSDATA"):
            logger.warning("QR login succeeded but no SESSDATA cookie could be retrieved (Bilibili may have changed the login flow again)")
            return state
        credential = _build_credential_from_cookies(cookies, ac_time_value)
        logger.info("Recovered QR login cookies from crossDomain Set-Cookie headers")
    else:
        credential = Credential(ac_time_value=ac_time_value)

    self._QrCodeLogin__credential = credential
    return QrCodeLoginEvents.DONE


async def qr_login() -> Credential:
    """QR code login via terminal.

    Displays a QR code in the terminal, polls until login completes,
    then saves and returns the credential.
    """
    login = QrCodeLogin()
    await login.generate_qrcode()

    # Display QR code in terminal
    print("\n📱 请使用 Bilibili App 扫描以下二维码登录:\n")
    print(_get_qr_terminal_output(login))
    print("\n⭐ 扫码后请在手机上确认登录...")

    # Poll login state
    while True:
        state = await login.check_state()

        if state == QrCodeLoginEvents.DONE:
            credential = login.get_credential()
            save_credential(credential)
            print("\n✅ 登录成功！凭证已保存")
            return credential

        elif state == QrCodeLoginEvents.TIMEOUT:
            raise RuntimeError("二维码已过期，请重试")

        elif state == QrCodeLoginEvents.CONF:
            print("  📲 已扫码，请在手机上确认...")

        await asyncio.sleep(2)


# Bilibili changed the WEB QR-login response format (2026-08): the success
# ``url`` is now a crossDomain ticket link and the cookies are delivered via
# Set-Cookie headers, which bilibili-api's ``login_v2.check_state`` (<=17.4.2)
# fails to parse (it only looks for cookies in the URL query string).  Install
# our own WEB poller that captures the credential at completion time; see
# ``_patched_check_state`` for details.  QR code generation (``generate_qrcode``)
# is unchanged and keeps working.
QrCodeLogin.check_state = _patched_check_state
