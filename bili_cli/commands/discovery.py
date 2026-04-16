"""Discovery commands (hot/rank)."""

from __future__ import annotations

import click
from rich.table import Table

from .. import payloads
from . import common


@click.command(name="hot")
@click.option("--page", "-p", default=1, type=click.IntRange(1), help="页码 (默认 1，最小 1)。")
@click.option("--max", "-n", "count", default=20, type=click.IntRange(1), help="显示数量 (默认 20，最小 1)。")
@common.structured_output_options
def hot_cmd(page: int, count: int, as_json: bool, as_yaml: bool):
    """查看热门视频。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    data = common.run_or_exit(client.get_hot_videos(pn=page, ps=count), "获取热门视频失败")

    if common.emit_structured(
        {
            "items": [payloads.normalize_video_summary(item) for item in (data.get("list") or [])[:count]],
            "page": page,
            "count": count,
        },
        output_format,
    ):
        return

    vlist = data.get("list") or []
    if not vlist:
        common.console.print("[yellow]未获取到热门视频[/yellow]")
        return

    table = Table(title="🔥 热门视频", border_style="red")
    table.add_column("#", style="dim", width=4)
    table.add_column("BV号", style="cyan", width=14)
    table.add_column("标题", max_width=36)
    table.add_column("UP主", width=12)
    table.add_column("播放", width=8, justify="right")
    table.add_column("点赞", width=8, justify="right")

    for i, v in enumerate(vlist[:count], 1):
        owner = v.get("owner", {})
        stat = v.get("stat", {})
        table.add_row(
            str(i),
            v.get("bvid", ""),
            v.get("title", "")[:36],
            owner.get("name", "")[:12],
            common.format_count(stat.get("view", 0)),
            common.format_count(stat.get("like", 0)),
        )

    common.console.print(table)


@click.command(name="rank")
@click.option("--day", default="3", type=click.Choice(["3", "7"]), help="排行周期：3 或 7 天（默认 3）。")
@click.option("--max", "-n", "count", default=20, type=click.IntRange(1), help="显示数量 (默认 20，最小 1)。")
@common.structured_output_options
def rank_cmd(day: str, count: int, as_json: bool, as_yaml: bool):
    """查看全站排行榜。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    data = common.run_or_exit(client.get_rank_videos(day=int(day)), "获取排行榜失败")

    if common.emit_structured(
        {
            "items": [payloads.normalize_video_summary(item) for item in (data.get("list") or [])[:count]],
            "day": int(day),
            "count": count,
        },
        output_format,
    ):
        return

    vlist = data.get("list") or []
    if not vlist:
        common.console.print("[yellow]未获取到排行榜数据[/yellow]")
        return

    table = Table(title="🏆 全站排行榜", border_style="yellow")
    table.add_column("#", style="bold", width=4)
    table.add_column("BV号", style="cyan", width=14)
    table.add_column("标题", max_width=36)
    table.add_column("UP主", width=12)
    table.add_column("播放", width=8, justify="right")
    table.add_column("综合分", width=8, justify="right")

    for i, v in enumerate(vlist[:count], 1):
        owner = v.get("owner", {})
        stat = v.get("stat", {})
        table.add_row(
            str(i),
            v.get("bvid", ""),
            v.get("title", "")[:36],
            owner.get("name", "")[:12],
            common.format_count(stat.get("view", 0)),
            str(v.get("score", "")),
        )

    common.console.print(table)
