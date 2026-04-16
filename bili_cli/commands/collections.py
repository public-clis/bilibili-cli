"""Collection and timeline related commands."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from .. import payloads
from . import common


def _decode_json(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_dynamic_id(item: dict[str, Any]) -> int:
    desc = item.get("desc", {}) if isinstance(item, dict) else {}
    candidates = [
        desc.get("dynamic_id"),
        desc.get("dynamic_id_str"),
        item.get("id_str"),
        item.get("id"),
    ]
    for candidate in candidates:
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str):
            try:
                return int(candidate)
            except ValueError:
                continue
    return 0


def _extract_dynamic_timestamp(item: dict[str, Any]) -> int:
    desc = item.get("desc", {}) if isinstance(item, dict) else {}
    ts = desc.get("timestamp")
    if isinstance(ts, int):
        return ts
    if isinstance(ts, str):
        try:
            return int(ts)
        except ValueError:
            return 0
    return 0


def _extract_dynamic_text(item: dict[str, Any]) -> str:
    parts: list[str] = []

    modules = item.get("modules", {}) if isinstance(item, dict) else {}
    if isinstance(modules, dict):
        dynamic_mod = modules.get("module_dynamic", {})
        if isinstance(dynamic_mod, dict):
            desc = dynamic_mod.get("desc", {})
            if isinstance(desc, dict) and isinstance(desc.get("text"), str):
                parts.append(desc["text"])

    card = _decode_json(item.get("card"))
    for key in ("title", "description", "dynamic", "summary"):
        value = card.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    card_item = card.get("item")
    if isinstance(card_item, dict):
        for key in ("title", "description", "content"):
            value = card_item.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())

    if not parts:
        desc = item.get("desc", {}) if isinstance(item, dict) else {}
        if isinstance(desc, dict):
            for key in ("description", "dynamic_id_str"):
                value = desc.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())

    return " ".join(parts).strip()


@click.command()
@click.argument("fav_id", required=False, type=int)
@click.option("--page", "-p", default=1, type=click.IntRange(1), help="页码 (默认 1，最小 1)。")
@common.structured_output_options
def favorites(fav_id: int | None, page: int, as_json: bool, as_yaml: bool):
    """浏览收藏夹。

    不带参数列出所有收藏夹，带 FAV_ID 查看收藏夹内的视频。
    """
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login(message="需要登录才能查看收藏夹。使用 [bold]bili login[/bold] 登录。")

    if fav_id is None:
        fav_list = common.run_or_exit(client.get_favorite_list(cred), "获取收藏夹列表失败")

        if common.emit_structured([payloads.normalize_favorite_folder(item) for item in fav_list], output_format):
            return

        if not fav_list:
            common.console.print("[yellow]未找到收藏夹[/yellow]")
            return

        table = Table(title="📂 收藏夹列表", border_style="blue")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("名称", width=20)
        table.add_column("视频数", width=10, justify="right")

        for f in fav_list:
            table.add_row(
                str(f.get("id", "")),
                f.get("title", ""),
                str(f.get("media_count", 0)),
            )

        common.console.print(table)
        common.console.print("\n[dim]使用 [bold]bili favorites <ID>[/bold] 查看收藏夹内容[/dim]")

    else:
        data = common.run_or_exit(
            client.get_favorite_videos(fav_id, cred, page=page),
            "获取收藏夹内容失败",
        )

        if common.emit_structured(
            {
                "folder_id": fav_id,
                "page": page,
                "has_more": bool(data.get("has_more", False)),
                "items": [payloads.normalize_favorite_media(item) for item in (data.get("medias") or [])],
            },
            output_format,
        ):
            return

        medias = data.get("medias") or []
        if not medias:
            common.console.print("[yellow]收藏夹为空或不存在[/yellow]")
            return

        table = Table(title=f"📂 收藏夹 #{fav_id}  (第 {page} 页)", border_style="blue")
        table.add_column("#", style="dim", width=4)
        table.add_column("BV号", style="cyan", width=14)
        table.add_column("标题", max_width=40)
        table.add_column("UP主", width=12)
        table.add_column("时长", width=8)

        for i, m in enumerate(medias, 1 + (page - 1) * 20):
            upper = m.get("upper", {})
            table.add_row(
                str(i),
                m.get("bvid", ""),
                (m.get("title", "") or "")[:40],
                (upper.get("name", "") or "")[:12],
                common.format_duration(m.get("duration", 0)),
            )

        common.console.print(table)

        has_more = data.get("has_more", False)
        if has_more:
            common.console.print(f"\n[dim]还有更多内容，使用 [bold]bili favorites {fav_id} --page {page + 1}[/bold] 查看下一页[/dim]")


@click.command()
@click.option("--page", "-p", default=1, type=click.IntRange(1), help="页码 (默认 1，最小 1)。")
@common.structured_output_options
def following(page: int, as_json: bool, as_yaml: bool):
    """查看关注列表。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login()

    me = common.run_or_exit(client.get_self_info(cred), "获取关注列表失败")
    uid = me["mid"]
    data = common.run_or_exit(
        client.get_followings(uid, pn=page, credential=cred),
        "获取关注列表失败",
    )

    if common.emit_structured(
        {
            "page": page,
            "total": data.get("total", 0),
            "items": [payloads.normalize_following_user(item) for item in (data.get("list") or [])],
        },
        output_format,
    ):
        return

    flist = data.get("list") or []
    if not flist:
        common.console.print("[yellow]关注列表为空[/yellow]")
        return

    total = data.get("total", "?")
    table = Table(title=f"🔔 关注列表  (共 {total}, 第 {page} 页)", border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("UID", style="cyan", width=12)
    table.add_column("用户名", width=16)
    table.add_column("签名", max_width=40)

    for i, u in enumerate(flist, 1 + (page - 1) * 20):
        table.add_row(
            str(i),
            str(u.get("mid", "")),
            u.get("uname", ""),
            (u.get("sign", "") or "")[:40],
        )

    common.console.print(table)
    common.console.print(f"\n[dim]使用 [bold]bili following --page {page + 1}[/bold] 查看下一页[/dim]")


@click.command()
@click.option("--page", "-p", default=1, type=click.IntRange(1), help="页码 (默认 1，最小 1)。")
@click.option("--max", "-n", "count", default=30, type=click.IntRange(1, 100), help="显示数量 (默认 30，1-100)。")
@common.structured_output_options
def history(page: int, count: int, as_json: bool, as_yaml: bool):
    """查看观看历史。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login()
    data = common.run_or_exit(
        client.get_watch_history(page=page, count=count, credential=cred),
        "获取观看历史失败",
    )

    if isinstance(data, list):
        vlist = data
    else:
        vlist = data.get("list") or data.get("items") or data.get("data") or []

    history_items = vlist if isinstance(vlist, list) else []
    if common.emit_structured(
        {
            "page": page,
            "count": min(count, len(history_items)) if history_items else 0,
            "items": [payloads.normalize_history_item(item) for item in history_items[:count] if isinstance(item, dict)],
        },
        output_format,
    ):
        return

    if not isinstance(vlist, list) or not vlist:
        common.console.print("[yellow]观看历史为空[/yellow]")
        return

    table = Table(title=f"🕘 观看历史  (第 {page} 页)", border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("标识", style="cyan", width=14)
    table.add_column("标题", max_width=36)
    table.add_column("UP主", width=12)
    table.add_column("观看时间", width=12)

    for i, v in enumerate(vlist[:count], 1):
        history_info = v.get("history", {}) if isinstance(v, dict) else {}
        owner = v.get("owner", {}) if isinstance(v, dict) else {}
        view_at = history_info.get("view_at") or (v.get("view_at", 0) if isinstance(v, dict) else 0)
        if isinstance(view_at, int) and view_at > 0:
            view_time = datetime.fromtimestamp(view_at).strftime("%m-%d %H:%M")
        else:
            view_time = "-"
        table.add_row(
            str(i),
            history_info.get("bvid") or v.get("bvid", "") or str(history_info.get("oid", "")),
            (v.get("title", "") or v.get("name", ""))[:36],
            (owner.get("name", "") or v.get("author_name", "") or v.get("author", ""))[:12],
            view_time,
        )

    common.console.print(table)


@click.command(name="watch-later")
@common.structured_output_options
def watch_later(as_json: bool, as_yaml: bool):
    """查看稍后再看列表。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login()

    data = common.run_or_exit(client.get_toview(cred), "获取稍后再看失败")

    if common.emit_structured(
        {
            "count": data.get("count", 0),
            "items": [payloads.normalize_watch_later_item(item) for item in (data.get("list") or [])],
        },
        output_format,
    ):
        return

    vlist = data.get("list") or []
    if not vlist:
        common.console.print("[yellow]稍后再看列表为空[/yellow]")
        return

    total = data.get("count", len(vlist))
    table = Table(title=f"⏰ 稍后再看  (共 {total} 个)", border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("BV号", style="cyan", width=14)
    table.add_column("标题", max_width=36)
    table.add_column("UP主", width=12)
    table.add_column("时长", width=8)

    for i, v in enumerate(vlist[:30], 1):
        owner = v.get("owner", {})
        table.add_row(
            str(i),
            v.get("bvid", ""),
            v.get("title", "")[:36],
            owner.get("name", "")[:12],
            common.format_duration(v.get("duration", 0)),
        )

    common.console.print(table)


@click.command()
@click.option("--offset", default="", help="分页游标；留空为最新。可使用上一页返回的 next_offset/offset。")
@common.structured_output_options
def feed(offset: str, as_json: bool, as_yaml: bool):
    """查看动态时间线。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login()

    data = common.run_or_exit(
        client.get_dynamic_feed(offset=offset, credential=cred),
        "获取动态失败",
    )

    items = data.get("items") or []
    if common.emit_structured(
        {
            "items": [payloads.normalize_dynamic_item(item) for item in items if isinstance(item, dict)],
            "next_offset": data.get("next_offset") or data.get("offset") or "",
        },
        output_format,
    ):
        return

    if not items:
        common.console.print("[yellow]暂无动态[/yellow]")
        return

    common.console.print("[bold]📰 动态时间线[/bold]\n")

    for item in items[:15]:
        modules = item.get("modules", {})
        author = modules.get("module_author", {})
        dyn_main = modules.get("module_dynamic", {})
        stat = modules.get("module_stat", {})

        name = author.get("name", "")
        pub_time = author.get("pub_time", "")

        desc = dyn_main.get("desc", {})
        text = desc.get("text", "") if desc else ""

        major = dyn_main.get("major", {})
        title = ""
        if major:
            archive = major.get("archive", {})
            if archive:
                title = archive.get("title", "")
            article = major.get("article", {})
            if article:
                title = article.get("title", "")

        comment_info = stat.get("comment", {})
        like_info = stat.get("like", {})
        comment_count = comment_info.get("count", 0) if comment_info else 0
        like_count = like_info.get("count", 0) if like_info else 0

        common.console.print(f"  [cyan]{name}[/cyan]  [dim]{pub_time}[/dim]")
        if title:
            common.console.print(f"  📺 {title}")
        if text:
            common.console.print(f"  {text[:100]}")
        if comment_count or like_count:
            common.console.print(f"  [dim]👍 {like_count}  💬 {comment_count}[/dim]")
        common.console.print()

    next_offset = data.get("next_offset") or data.get("offset")
    if next_offset not in ("", None):
        common.console.print(f"[dim]下一页：bili feed --offset {next_offset}[/dim]")


@click.command(name="my-dynamics")
@click.option("--offset", default=0, type=click.IntRange(0), help="分页偏移量；默认 0。")
@click.option("--top/--no-top", "need_top", default=False, help="是否包含置顶动态。")
@click.option("--max", "-n", "count", default=20, type=click.IntRange(1, 50), help="显示条数 (1-50)。")
@common.structured_output_options
def my_dynamics(offset: int, need_top: bool, count: int, as_json: bool, as_yaml: bool):
    """查看我发布的动态。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login()

    me = common.run_or_exit(client.get_self_info(cred), "获取我的动态失败")
    uid = me.get("mid")
    if not isinstance(uid, int):
        common.exit_error("获取我的动态失败: 当前用户信息缺少 mid")

    data = common.run_or_exit(
        client.get_user_dynamics(uid=uid, offset=offset, need_top=need_top, credential=cred),
        "获取我的动态失败",
    )

    cards = data.get("cards") or []
    if common.emit_structured(
        {
            "offset": offset,
            "next_offset": data.get("next_offset") or data.get("offset") or "",
            "items": [payloads.normalize_dynamic_item(card) for card in cards[:count] if isinstance(card, dict)],
        },
        output_format,
    ):
        return

    if not isinstance(cards, list) or not cards:
        common.console.print("[yellow]暂无我发布的动态[/yellow]")
        return

    table = Table(title=f"📝 我的动态  (offset={offset})", border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("动态ID", style="cyan", width=16)
    table.add_column("发布时间", width=12)
    table.add_column("内容", max_width=60)

    for idx, card in enumerate(cards[:count], 1):
        if not isinstance(card, dict):
            continue
        dynamic_id = _extract_dynamic_id(card)
        ts = _extract_dynamic_timestamp(card)
        pub_time = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts > 0 else "-"
        text = _extract_dynamic_text(card)[:60] or "-"
        table.add_row(str(idx), str(dynamic_id), pub_time, text)

    common.console.print(table)

    next_offset = data.get("next_offset") or data.get("offset")
    if next_offset not in ("", None, offset):
        common.console.print(f"\n[dim]下一页：bili my-dynamics --offset {next_offset}[/dim]")


@click.command(name="dynamic-post")
@click.argument("text", required=False)
@click.option(
    "--from-file",
    "from_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="从文件读取动态文本。",
)
@common.structured_output_options
def dynamic_post(text: str | None, from_file: Path | None, as_json: bool, as_yaml: bool):
    """发布一条纯文本动态。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login(require_write=True)
    raw_text = text or ""
    if from_file is not None:
        raw_text = from_file.read_text(encoding="utf-8")

    content = raw_text.strip()
    if not content:
        common.exit_error("请提供动态文本。可用参数：TEXT 或 --from-file FILE")

    data = common.run_or_exit(
        client.post_text_dynamic(content, credential=cred),
        "发布动态失败",
    )

    dynamic_id = data.get("dynamic_id") or data.get("dynamic_id_str") or data.get("dyn_id")
    if common.emit_structured(
        payloads.action_result("dynamic_post", dynamic_id=str(dynamic_id or ""), text=content),
        output_format,
    ):
        return

    if dynamic_id:
        common.console.print(f"[green]✅ 已发布动态: {dynamic_id}[/green]")
    else:
        common.console.print("[green]✅ 已发布动态[/green]")


@click.command(name="dynamic-delete")
@click.argument("dynamic_id", type=int)
@click.option("--yes", is_flag=True, help="跳过确认，直接删除。")
@common.structured_output_options
def dynamic_delete(dynamic_id: int, yes: bool, as_json: bool, as_yaml: bool):
    """删除一条动态。"""
    from .. import client

    output_format = common.resolve_output_format(as_json=as_json, as_yaml=as_yaml)

    cred = common.require_login(require_write=True)

    if not yes:
        confirmed = click.confirm(f"确认删除动态 {dynamic_id} 吗？", default=False)
        if not confirmed:
            common.console.print("[yellow]已取消删除[/yellow]")
            return

    common.run_or_exit(
        client.delete_dynamic(dynamic_id=dynamic_id, credential=cred),
        "删除动态失败",
    )

    if common.emit_structured(
        payloads.action_result("dynamic_delete", dynamic_id=str(dynamic_id)),
        output_format,
    ):
        return

    common.console.print(f"[green]🗑️ 已删除动态: {dynamic_id}[/green]")
