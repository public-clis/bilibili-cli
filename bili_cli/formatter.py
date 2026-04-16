"""Shared formatting utilities for bilibili-cli output.

Centralizes structured output (JSON/YAML), number formatting, and the
agent-friendly schema envelope shared across all command modules.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from typing import NoReturn

import click
import yaml
from rich.console import Console

console = Console(stderr=True)
OutputFormat = str | None
_OUTPUT_ENV = "OUTPUT"
_SCHEMA_VERSION = "1"


def structured_output_options(command: Callable) -> Callable:
    """Add --json/--yaml options to a Click command."""
    command = click.option("--yaml", "as_yaml", is_flag=True, help="输出 YAML，推荐给 AI Agent。")(command)
    command = click.option("--json", "as_json", is_flag=True, help="输出 JSON。")(command)
    return command


def resolve_output_format(*, as_json: bool = False, as_yaml: bool = False) -> OutputFormat:
    """Resolve mutually exclusive machine-readable output flags."""
    if as_json and as_yaml:
        exit_error("不能同时使用 --json 和 --yaml。")
    if as_yaml:
        return "yaml"
    if as_json:
        return "json"
    output_mode = os.getenv(_OUTPUT_ENV, "auto").strip().lower()
    if output_mode == "yaml":
        return "yaml"
    if output_mode == "json":
        return "json"
    if output_mode == "rich":
        return None
    if not sys.stdout.isatty():
        return "yaml"
    return None


def emit_structured(data: object, output_format: OutputFormat) -> bool:
    """Serialize data for machine-readable output and report whether emission happened."""
    payload = _normalize_success_payload(data)
    if output_format == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return True
    if output_format == "yaml":
        click.echo(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
        return True
    return False


def emit_or_print(data: object, output_format: OutputFormat, render: Callable[[], None]) -> bool:
    """Emit structured data or fall back to a rich/text renderer."""
    if emit_structured(data, output_format):
        return True
    render()
    return False


def success_payload(data: object) -> dict[str, object]:
    """Wrap structured success data in the shared agent schema."""
    return {
        "ok": True,
        "schema_version": _SCHEMA_VERSION,
        "data": data,
    }


def error_payload(code: str, message: str, *, details: object | None = None) -> dict[str, object]:
    """Wrap structured error data in the shared agent schema."""
    error: dict[str, object] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error["details"] = details
    return {
        "ok": False,
        "schema_version": _SCHEMA_VERSION,
        "error": error,
    }


def _normalize_success_payload(data: object) -> object:
    """Wrap plain structured data in the shared agent success schema."""
    if isinstance(data, dict) and data.get("schema_version") == _SCHEMA_VERSION and "ok" in data:
        return data
    return success_payload(data)


def exit_error(message: str, *, code: str = "api_error", details: object | None = None) -> NoReturn:
    """Print an error message and exit with non-zero status."""
    ctx = click.get_current_context(silent=True)
    params = ctx.params if ctx is not None else {}
    as_json = bool(params.get("as_json", False))
    as_yaml = bool(params.get("as_yaml", False))
    output_format = None if as_json and as_yaml else resolve_output_format(as_json=as_json, as_yaml=as_yaml)
    if emit_structured(error_payload(code, message, details=details), output_format):
        sys.exit(1)
    console.print(f"[red]❌ {message}[/red]")
    sys.exit(1)


# ── Display formatting ────────────────────────────────────────────────────


def _to_int(value: object, default: int = 0) -> int:
    """Best-effort convert value to int for display-oriented formatting."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def format_duration(seconds: object) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    seconds_int = _to_int(seconds, default=0)
    if seconds_int < 0:
        seconds_int = 0
    if seconds_int >= 3600:
        h, rem = divmod(seconds_int, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"
    m, s = divmod(seconds_int, 60)
    return f"{m:02d}:{s:02d}"


def format_count(n: object) -> str:
    """Format large numbers with 万 suffix."""
    value = _to_int(n, default=0)
    if value >= 10000:
        return f"{value / 10000:.1f}万"
    return str(value)
