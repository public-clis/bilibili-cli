"""Account and authentication related commands."""

from __future__ import annotations

import sys

import click
from rich.panel import Panel

from .. import payloads
from . import common


@click.command()
def login():
    """扫码登录 Bilibili。"""
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
