"""User and search related commands."""

from __future__ import annotations

import re

import click
from rich.panel import Panel
from rich.table import Table

from .. import payloads
from . import common


def _resolve_uid(uid_or_name: str) -> int:
    """Resolve a UID or username to a numeric UID."""
    from .. import client

    if uid_or_name.isdigit():
        return int(uid_or_name)

    results = common.run_or_exit(client.search_user(uid_or_name), "搜索用户失败")
    if not results:
        common.exit_error(f"未找到用户: {uid_or_name}", code="not_found")

    uid_raw = results[0].get("mid")
    if uid_raw is None:
        common.exit_error(f"搜索结果缺少 UID: {uid_or_name}", code="upstream_error")

    try:
        uid = int(uid_raw)
    except (TypeError, ValueError):
        common.exit_error(f"搜索结果 UID 非法: {uid_raw}", code="upstream_error")

    common.console.print(f"[dim]🔍 匹配到: {results[0].get('uname', '')} (UID: {uid})[/dim]\n")
    return uid


def _format_video_length(length_raw: object) -> str:
    """Normalize different video length payloads into display string."""
    if isinstance(length_raw, str):
        if ":" in length_raw:
            return length_raw
        if not length_raw:
            return "00:00"
        try:
            return common.format_duration(int(length_raw))
        except ValueError:
            return "00:00"

    if isinstance(length_raw, int):
        return common.format_duration(length_raw)

    return "00:00"


@click.command()
@click.argument("uid_or_name")
@common.structured_output_options
def user(uid_or_name: str, as_json: bool, as_yaml: bool):
    """查看 UP 主资料。

    UID_OR_NAME 可以是 UID（纯数字）或用户名（搜索第一个匹配）。
    """
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    uid = _resolve_uid(uid_or_name)

    info = common.run_or_exit(client.get_user_info(uid, credential=None), "获取用户信息失败")
    relation = common.run_or_exit(
        client.get_user_relation_info(uid, credential=None),
        "获取用户信息失败",
    )

    structured = {
        "user": payloads.normalize_user(info),
        "relation": payloads.normalize_relation(relation),
    }
    if common.emit_structured(structured, output_format):
        return

    follower = relation.get("follower", 0)
    following = relation.get("following", 0)

    common.console.print(Panel(
        f"👤 [bold]{info.get('name', '')}[/bold]  (UID: {uid})\n"
        f"⭐ Level {info.get('level', '?')}  |  "
        f"👥 粉丝 {common.format_count(follower)}  |  "
        f"🔔 关注 {common.format_count(following)}",
        title="UP 主信息",
        border_style="cyan",
    ))

    sign = info.get("sign", "").strip()
    if sign:
        common.console.print(f"[dim]{sign}[/dim]")


@click.command(name="user-videos")
@click.argument("uid_or_name")
@click.option("--max", "-n", "count", default=10, type=click.IntRange(1), help="显示的视频数量 (默认 10，最小 1)。")
@common.structured_output_options
def user_videos(uid_or_name: str, count: int, as_json: bool, as_yaml: bool):
    """查看 UP 主的视频列表。

    UID_OR_NAME 可以是 UID（纯数字）或用户名（搜索第一个匹配）。
    """
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    uid = _resolve_uid(uid_or_name)

    videos = common.run_or_exit(
        client.get_user_videos(uid, count=count, credential=None),
        "获取视频列表失败",
    )

    if common.emit_structured([payloads.normalize_video_summary(video) for video in videos], output_format):
        return

    if not videos:
        common.console.print("[yellow]该用户暂无视频[/yellow]")
        return

    table = Table(title=f"最新 {len(videos)} 个视频", border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("BV号", style="cyan", width=14)
    table.add_column("标题", max_width=40)
    table.add_column("时长", width=8)
    table.add_column("播放", width=8, justify="right")

    for i, v in enumerate(videos, 1):
        length_str = _format_video_length(v.get("length", "0"))
        table.add_row(
            str(i),
            v.get("bvid", ""),
            v.get("title", "")[:40],
            length_str,
            common.format_count(v.get("play", 0)),
        )

    common.console.print(table)


@click.command()
@click.argument("keyword")
@click.option("--type", "search_type", default="user", type=click.Choice(["user", "video"]), help="搜索类型 (默认 user)。")
@click.option("--page", default=1, type=click.IntRange(1), help="页码 (默认 1，最小 1)。")
@click.option("--max", "-n", "count", default=20, type=click.IntRange(1), help="显示数量 (默认 20，最小 1)。")
@common.structured_output_options
def search(keyword: str, search_type: str, page: int, count: int, as_json: bool, as_yaml: bool):
    """搜索用户或视频。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    if search_type == "video":
        results = common.run_or_exit(client.search_video(keyword, page=page), "搜索视频失败")

        if common.emit_structured([payloads.normalize_search_video(item) for item in results[:count]], output_format):
            return

        display_results = [v for v in results if v.get("bvid")]
        if not display_results:
            common.console.print(f"[yellow]未找到与 '{keyword}' 相关的视频[/yellow]")
            return

        table = Table(title=f"🔍 视频搜索: {keyword}", border_style="blue")
        table.add_column("#", style="dim", width=4)
        table.add_column("BV号", style="cyan", width=14)
        table.add_column("标题", max_width=40)
        table.add_column("UP主", width=12)
        table.add_column("播放", width=10, justify="right")
        table.add_column("时长", width=8)

        for i, v in enumerate(display_results[:count], 1):
            title = re.sub(r'<[^>]+>', '', v.get("title", ""))[:40]
            table.add_row(
                str(i),
                v.get("bvid", ""),
                title,
                v.get("author", "")[:12],
                common.format_count(v.get("play", 0)),
                v.get("duration", ""),
            )

        common.console.print(table)
    else:
        results = common.run_or_exit(client.search_user(keyword, page=page), "搜索用户失败")

        if common.emit_structured([payloads.normalize_search_user(item) for item in results[:count]], output_format):
            return

        if not results:
            common.console.print(f"[yellow]未找到与 '{keyword}' 相关的用户[/yellow]")
            return

        table = Table(title=f"🔍 搜索: {keyword}", border_style="blue")
        table.add_column("UID", style="cyan", width=12)
        table.add_column("用户名", width=20)
        table.add_column("粉丝", width=10, justify="right")
        table.add_column("视频数", width=8, justify="right")
        table.add_column("签名", max_width=40)

        for u in results[:count]:
            usign = u.get("usign", "")
            table.add_row(
                str(u.get("mid", "")),
                u.get("uname", ""),
                common.format_count(u.get("fans", 0)),
                str(u.get("videos", 0)),
                usign[:40] if usign else "",
            )

        common.console.print(table)
