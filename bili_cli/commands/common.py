"""Shared helpers for CLI command modules."""

from __future__ import annotations

import logging
import sys

import click

from .. import auth
from ..exceptions import AuthenticationError, BiliError, InvalidBvidError, NetworkError, NotFoundError, RateLimitError

# Re-export all formatting utilities from formatter.py for backward compatibility.
# Command modules do `from .common import emit_structured, format_count, ...`
from ..formatter import (  # noqa: F401
    OutputFormat,
    _to_int,
    console,
    emit_or_print,
    emit_structured,
    error_payload,
    exit_error,
    format_count,
    format_duration,
    resolve_output_format,
    structured_output_options,
    success_payload,
)


def setup_logging(verbose: bool):
    """Configure global logging based on CLI verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s: %(message)s")


def run(coro):
    """Bridge async coroutine into synchronous click command."""
    import asyncio
    return asyncio.run(coro)


def run_or_exit(coro, action: str):
    """Run async call and convert unexpected errors to CLI-friendly failures."""
    try:
        return run(coro)
    except InvalidBvidError as e:
        exit_error(f"{action}: {e}", code="invalid_input")
    except AuthenticationError as e:
        exit_error(f"{action}: {e}", code="not_authenticated")
    except RateLimitError as e:
        exit_error(f"{action}: {e}", code="rate_limited")
    except NotFoundError as e:
        exit_error(f"{action}: {e}", code="not_found")
    except NetworkError as e:
        exit_error(f"{action}: {e}", code="network_error")
    except BiliError as e:
        exit_error(f"{action}: {e}", code="upstream_error")
    except Exception as e:
        exit_error(f"{action}: {e}", code="internal_error")


def get_credential(mode: auth.AuthMode = "read"):
    """Read credential from configured auth strategy."""
    return auth.get_credential(mode=mode)


def clear_credential():
    """Remove saved credential."""
    return auth.clear_credential()


def qr_login():
    """Return login coroutine for QR login flow."""
    return auth.qr_login()


def print_login_required(message: str | None = None):
    """Print a standard login-required warning message."""
    if message:
        console.print(f"[yellow]⚠️  {message}[/yellow]")
        return
    console.print("[yellow]⚠️  需要登录。使用 [bold]bili login[/bold] 登录。[/yellow]")


def require_login(require_write: bool = False, message: str | None = None):
    """Require login credential and optional write capability."""
    mode: auth.AuthMode = "write" if require_write else "read"
    cred = get_credential(mode=mode)
    if cred:
        return cred

    if require_write:
        # Diagnose a common case: saved session exists but lacks bili_jct.
        saved = get_credential(mode="optional")
        if saved and getattr(saved, "sessdata", "") and not getattr(saved, "bili_jct", ""):
            exit_error(
                "当前登录凭证不支持写操作（缺少 bili_jct）。请执行 bili login 重新登录。",
                code="permission_denied",
            )

    ctx = click.get_current_context(silent=True)
    params = ctx.params if ctx is not None else {}
    output_format = resolve_output_format(
        as_json=bool(params.get("as_json", False)),
        as_yaml=bool(params.get("as_yaml", False)),
    )
    error_message = message or "未登录。使用 bili login 登录。"
    if emit_structured(error_payload("not_authenticated", error_message), output_format):
        sys.exit(1)
    print_login_required(message)
    sys.exit(1)


def run_optional(coro, action: str):
    """Run optional sub-request and print warning on failure."""
    try:
        return run(coro)
    except BiliError as e:
        console.print(f"[yellow]⚠️  {action}: {e}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️  {action}: {e}[/yellow]")
    return None


def extract_bvid_or_exit(bv_or_url: str) -> str:
    """Extract BV ID from input; print a user-friendly error on failure."""
    from .. import client

    try:
        return client.extract_bvid(bv_or_url)
    except (InvalidBvidError, ValueError) as e:
        exit_error(str(e), code="invalid_input")
