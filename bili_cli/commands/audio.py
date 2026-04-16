"""Audio extraction command — download and split video audio for ASR."""

from __future__ import annotations

import os
import re
import tempfile

import click

from .common import console, exit_error, extract_bvid_or_exit, get_credential, run_or_exit

DEFAULT_TMP_DIR = os.path.join(tempfile.gettempdir(), "bilibili-cli")


def _sanitize_filename(title: str) -> str:
    """Remove or replace characters that are unsafe in file paths."""
    title = re.sub(r'[<>:"/\\|?*]', "_", title)
    title = title.strip(". ")
    return title[:120] or "audio"


@click.command()
@click.argument("bv_or_url")
@click.option("--segment", "-s", default=25, type=click.IntRange(5, 300),
              help="每段时长（秒），默认 25。")
@click.option("--no-split", is_flag=True, help="不切分，直接保存完整音频文件。")
@click.option("--output", "-o", default=None, type=click.Path(),
              help=f"输出目录（默认 {DEFAULT_TMP_DIR}/{{title}}/）。")
def audio(bv_or_url: str, segment: int, no_split: bool, output: str | None):
    """下载视频音频并切分为 ASR-ready WAV 片段。

    默认输出到 /tmp/bilibili-cli/{title}/ 目录，
    每段 25 秒，16kHz mono PCM WAV 格式，可直接用于语音转文字 API。

    \b
    示例:
      bili audio BV1ABcsztEcY                  # 下载并切分
      bili audio BV1ABcsztEcY --segment 60     # 每段 60 秒
      bili audio BV1ABcsztEcY --no-split       # 保存完整 m4a
      bili audio BV1ABcsztEcY -o ~/data/       # 自定义输出目录
    """
    from .. import client

    bvid = extract_bvid_or_exit(bv_or_url)

    # 1. Get video info for title
    cred = get_credential(mode="optional")
    info = run_or_exit(client.get_video_info(bvid, credential=cred), "获取视频信息")
    title = info.get("title", bvid)
    duration = info.get("duration", 0)
    safe_title = _sanitize_filename(title)

    console.print(f"[bold]🎵 {title}[/bold]  ({_format_time(duration)})")

    # 2. Get audio stream URL
    console.print("[dim]获取音频流地址...[/dim]")
    audio_url = run_or_exit(client.get_audio_url(bvid, credential=cred), "获取音频流")

    # 3. Determine output directory
    if output:
        out_dir = os.path.expanduser(output)
    else:
        out_dir = os.path.join(DEFAULT_TMP_DIR, safe_title)

    if no_split:
        # Download full audio without splitting
        out_file = os.path.join(out_dir, f"{safe_title}.m4a")
        console.print("[dim]下载音频中...[/dim]")
        nbytes = run_or_exit(client.download_audio(audio_url, out_file), "下载音频")
        size_mb = nbytes / (1024 * 1024)
        console.print(f"[green]✅ 音频已保存: {out_file} ({size_mb:.1f} MB)[/green]")
    else:
        # Download to temp file, then split
        os.makedirs(out_dir, exist_ok=True)
        tmp_path = os.path.join(out_dir, "_raw.m4s")

        console.print("[dim]下载音频中...[/dim]")
        nbytes = run_or_exit(client.download_audio(audio_url, tmp_path), "下载音频")
        size_mb = nbytes / (1024 * 1024)
        console.print(f"[dim]下载完成 ({size_mb:.1f} MB)，切分中...[/dim]")

        try:
            segments = client.split_audio(tmp_path, out_dir, segment_seconds=segment)
        except Exception as e:
            exit_error(f"音频切分失败: {e}")
        finally:
            # Clean up raw download
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        console.print(f"[green]✅ 切分完成: {len(segments)} 段 (每段 ~{segment}s)[/green]")
        console.print(f"[green]   输出目录: {out_dir}[/green]")
        for _i, seg in enumerate(segments):
            basename = os.path.basename(seg)
            size_kb = os.path.getsize(seg) / 1024
            console.print(f"[dim]   {basename}  ({size_kb:.0f} KB)[/dim]")


def _format_time(seconds: int) -> str:
    """Format duration for display."""
    if seconds >= 3600:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"
