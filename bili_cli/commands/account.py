"""Account and authentication related commands."""

from __future__ import annotations

import sys

import click
from rich.panel import Panel

from .. import payloads
from ..auth import SUPPORTED_BROWSERS
from . import common

_STATUS_LABELS: dict[str, str] = {
    "found": "[green]找到有效 Cookie[/green]",
    "no_cookie": "[dim]未找到 bilibili Cookie[/dim]",
    "error": "[dim]无法访问（未安装或无权限）[/dim]",
    "probe_failed": "[dim]探测失败[/dim]",
}


def _print_browser_attempts(attempts: list[dict[str, str]]) -> None:
    """Print per-browser probe results to the terminal."""
    for a in attempts:
        label = _STATUS_LABELS.get(a["status"], a["status"])
        common.console.print(f"  {a['browser']:<12} {label}")


@click.command()
@click.option(
    "--browser", "-b",
    type=click.Choice(SUPPORTED_BROWSERS, case_sensitive=False),
    default=None,
    help="仅从指定浏览器提取 cookie（跳过其他浏览器和扫码）。",
)
@click.option(
    "--cookie-file", "-c",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="从 JSON 文件加载 cookie（适用于非常规浏览器）。",
)
def login(browser: str | None, cookie_file: str | None):
    """登录 Bilibili。

    默认依次尝试所有浏览器，失败后启动扫码登录。
    可用 --browser 指定浏览器，或 --cookie-file 导入 cookie 文件。
    """
    from ..auth import (
        _validate_credential,
        load_credential_from_cookie_file,
        probe_browser_cookies,
        save_credential,
    )

    if cookie_file:
        try:
            file_cred = load_credential_from_cookie_file(cookie_file)
        except (FileNotFoundError, ValueError) as e:
            common.exit_error(str(e))
            return
        save_credential(file_cred)
        common.console.print("[green]✅ 已从 cookie 文件加载凭证并保存！[/green]")
        return

    common.console.print("[bold]🔍 正在尝试从本地浏览器提取 Cookie...[/bold]")
    cred, attempts = probe_browser_cookies(browser_name=browser)
    _print_browser_attempts(attempts)

    if cred:
        found_name = next((a["browser"] for a in attempts if a["status"] == "found"), "browser")
        validation = _validate_credential(cred)
        if validation is False:
            common.console.print(
                f"\n[yellow]⚠️  从 {found_name} 提取的 Cookie 已过期或无效，"
                "请重新在浏览器登录 bilibili.com。[/yellow]"
            )
        else:
            save_credential(cred)
            common.console.print(f"\n[green]✅ 已从 {found_name} 提取 Cookie 并保存！[/green]")
            return

    if browser:
        common.exit_error(f"无法从 {browser} 提取有效 Cookie。请确保已在该浏览器登录 bilibili.com。")

    common.console.print("\n[yellow]⚠️  未能从任何浏览器提取到有效的 bilibili Cookie[/yellow]")
    common.console.print("[bold]📱 正在启动二维码登录...[/bold]\n")

    try:
        common.run(common.qr_login())
    except RuntimeError as e:
        common.exit_error(str(e))
    except Exception as e:
        common.exit_error(f"登录失败: {e}")


@click.command()
def logout():
    """注销并清除保存的凭证。"""
    common.clear_credential()
    common.console.print("[green]✅ 已注销，凭证已清除[/green]")


@click.command()
@common.structured_output_options
def status(as_json: bool, as_yaml: bool):
    """检查登录状态。"""
    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)
    cred = common.get_credential(mode="read")
    if not cred:
        payload = common.error_payload("not_authenticated", "未登录。使用 bili login 登录。")
        if common.emit_structured(payload, output_format):
            raise SystemExit(1) from None
        common.print_login_required("未登录。使用 [bold]bili login[/bold] 登录。")
        sys.exit(1)

    from .. import client

    try:
        info = common.run(client.get_self_info(cred))
    except Exception as exc:
        payload = common.error_payload("api_error", f"检查登录状态失败: {exc}")
        if common.emit_structured(payload, output_format):
            raise SystemExit(1) from None
        common.exit_error(f"检查登录状态失败: {exc}")

    payload = common.success_payload(
        {
            "authenticated": True,
            "user": payloads.normalize_user(info),
        }
    )
    def render() -> None:
        name = info.get("name", "unknown")
        uid = info.get("mid", "unknown")
        common.console.print(f"[green]✅ 已登录：[bold]{name}[/bold]  (UID: {uid})[/green]")

    if common.emit_or_print(payload, output_format, render):
        return


@click.command()
@common.structured_output_options
def whoami(as_json: bool, as_yaml: bool):
    """查看当前登录用户的详细信息。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.get_credential(mode="read")
    if not cred:
        payload = common.error_payload("not_authenticated", "未登录。使用 bili login 登录。")
        if common.emit_structured(payload, output_format):
            raise SystemExit(1) from None
        common.print_login_required("未登录。使用 [bold]bili login[/bold] 登录。")
        sys.exit(1)

    try:
        info = common.run(client.get_self_info(cred))
        uid = info.get("mid", "unknown")
        relation = common.run(client.get_user_relation_info(uid, credential=cred))
    except Exception as exc:
        payload = common.error_payload("api_error", f"获取用户信息失败: {exc}")
        if common.emit_structured(payload, output_format):
            raise SystemExit(1) from None
        common.exit_error(f"获取用户信息失败: {exc}")

    payload = common.success_payload(
        {"user": payloads.normalize_user(info), "relation": payloads.normalize_relation(relation)}
    )

    def render() -> None:
        name = info.get("name", "unknown")
        level = info.get("level", "?")
        coins = info.get("coins", 0)
        follower = relation.get("follower", 0)
        following = relation.get("following", 0)

        vip = info.get("vip", {})
        vip_label = ""
        if vip.get("status") == 1:
            vip_type = "大会员" if vip.get("type") == 2 else "小会员"
            vip_label = f"  |  🏅 {vip_type}"

        sign = info.get("sign", "").strip()

        lines = [
            f"👤 [bold]{name}[/bold]  (UID: {uid})",
            f"⭐ Level {level}  |  🪙 硬币 {coins}{vip_label}",
            f"👥 粉丝 {common.format_count(follower)}  |  🔔 关注 {common.format_count(following)}",
        ]
        if sign:
            lines.append(f"📝 {sign}")

        common.console.print(Panel(
            "\n".join(lines),
            title="个人信息",
            border_style="green",
        ))

    if common.emit_or_print(payload, output_format, render):
        return
