"""Cover image download command — download video cover art."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import click

from .common import DEFAULT_TMP_DIR, console, exit_error, extract_bvid_or_exit, get_credential, run_or_exit, sanitize_filename


def _url_extension(url: str, default: str = ".jpg") -> str:
    """Extract the file extension from a URL path."""
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext if ext else default


@click.command()
@click.argument("bv_or_url")
@click.option("--output", "-o", default=None, type=click.Path(),
              help=f"输出路径或目录（默认 {DEFAULT_TMP_DIR}/{{title}}/{{title}}.{{ext}}）。")
def cover(bv_or_url: str, output: str | None):
    """下载视频封面图。

    默认输出到 /tmp/bilibili-cli/{title}/{title}.{ext}（文件名取视频标题，扩展名从封面 URL 自动识别），
    若 -o 指定目录则存为 {目录}/{title}.{ext}，
    若 -o 指定文件路径则直接使用。

    \b
    示例:
      bili cover BV1ABcsztEcY                        # 下载到临时目录
      bili cover BV1ABcsztEcY -o ~/Pictures/          # 存到指定目录
      bili cover BV1ABcsztEcY -o ~/cover.png          # 存为指定文件
      bili cover https://www.bilibili.com/video/BV1xx  # 支持 URL
    """
    from .. import client

    bvid = extract_bvid_or_exit(bv_or_url)

    # 1. Get video info for title and cover URL
    cred = get_credential(mode="optional")
    info = run_or_exit(client.get_video_info(bvid, credential=cred), "获取视频信息")
    title = info.get("title", bvid)
    safe_title = sanitize_filename(title, fallback="cover")
    cover_url = run_or_exit(client.get_cover_url(bvid, credential=cred), "获取封面地址")

    console.print(f"[bold]🖼️ {title}[/bold]")

    # 2. Determine output path
    ext = _url_extension(cover_url)

    if output:
        output_path = os.path.expanduser(output)
        # If output looks like a directory (ends with separator or has no extension), treat as directory
        if os.path.isdir(output_path) or output_path.endswith(os.sep) or "." not in os.path.basename(output_path):
            os.makedirs(output_path, exist_ok=True)
            output_path = os.path.join(output_path, f"{safe_title}{ext}")
    else:
        out_dir = os.path.join(DEFAULT_TMP_DIR, safe_title)
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, f"{safe_title}{ext}")

    # 3. Download cover
    console.print(f"[dim]下载封面中...[/dim]")
    nbytes = run_or_exit(client.download_image(cover_url, output_path), "下载封面")
    size_str = f"{nbytes / 1024:.1f} KB" if nbytes < 1024 * 1024 else f"{nbytes / (1024 * 1024):.1f} MB"
    console.print(f"[green]✅ 封面已保存: {output_path} ({size_str})[/green]")
