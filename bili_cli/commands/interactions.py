"""Video interaction commands."""

from __future__ import annotations

import click

from .. import payloads
from . import common


@click.command()
@click.argument("bv_or_url")
@click.option("--undo", is_flag=True, help="取消点赞。")
@common.structured_output_options
def like(bv_or_url: str, undo: bool, as_json: bool, as_yaml: bool):
    """点赞视频。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)
    cred = common.require_login(require_write=True)
    bvid = common.extract_bvid_or_exit(bv_or_url)

    common.run_or_exit(client.like_video(bvid, credential=cred, undo=undo), "操作失败")
    payload = payloads.action_result("unlike" if undo else "like", bvid=bvid, undo=undo)

    def render() -> None:
        if undo:
            common.console.print(f"[yellow]👎 已取消点赞: {bvid}[/yellow]")
        else:
            common.console.print(f"[green]👍 已点赞: {bvid}[/green]")

    if common.emit_or_print(payload, output_format, render):
        return


@click.command()
@click.argument("bv_or_url")
@click.option("--num", "-n", default=1, type=click.IntRange(1, 2), help="投币数量 (1 或 2)。")
@common.structured_output_options
def coin(bv_or_url: str, num: int, as_json: bool, as_yaml: bool):
    """给视频投币。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)
    cred = common.require_login(require_write=True)
    bvid = common.extract_bvid_or_exit(bv_or_url)

    common.run_or_exit(client.coin_video(bvid, credential=cred, num=num), "投币失败")
    payload = payloads.action_result("coin", bvid=bvid, coins=num)

    def render() -> None:
        common.console.print(f"[green]🪙 已投 {num} 枚硬币: {bvid}[/green]")

    if common.emit_or_print(payload, output_format, render):
        return


@click.command()
@click.argument("bv_or_url")
@common.structured_output_options
def triple(bv_or_url: str, as_json: bool, as_yaml: bool):
    """一键三连（点赞 + 投币 + 收藏）。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)
    cred = common.require_login(require_write=True)
    bvid = common.extract_bvid_or_exit(bv_or_url)

    result = common.run_or_exit(client.triple_video(bvid, credential=cred), "三连失败")
    parts = []
    if result.get("like"):
        parts.append("👍 点赞")
    if result.get("coin"):
        parts.append("🪙 投币")
    if result.get("multiply") or result.get("fav"):
        parts.append("⭐ 收藏")
    payload = payloads.action_result(
        "triple",
        bvid=bvid,
        result={
            "like": bool(result.get("like")),
            "coin": bool(result.get("coin")),
            "favorite": bool(result.get("multiply") or result.get("fav")),
        },
    )

    def render() -> None:
        common.console.print(f"[green]🎉 一键三连成功: {bvid}[/green]")
        if parts:
            common.console.print(f"[dim]  {' + '.join(parts)}[/dim]")

    if common.emit_or_print(payload, output_format, render):
        return


@click.command()
@click.argument("uid", type=int)
@click.option("--yes", is_flag=True, help="跳过确认，直接取消关注。")
@common.structured_output_options
def unfollow(uid: int, yes: bool, as_json: bool, as_yaml: bool):
    """取消关注某个 UP（按 UID）。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login(require_write=True)

    if not yes:
        confirmed = click.confirm(f"确认取消关注 UID={uid} 吗？", default=False)
        if not confirmed:
            common.console.print("[yellow]已取消操作[/yellow]")
            return

    common.run_or_exit(
        client.unfollow_user(uid=uid, credential=cred),
        "取消关注失败",
    )

    payload = payloads.action_result("unfollow", uid=uid)

    def render() -> None:
        common.console.print(f"[green]✅ 已取消关注 UID={uid}[/green]")

    if common.emit_or_print(payload, output_format, render):
        return
