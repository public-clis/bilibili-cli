"""CLI entry point for bilibili-cli.

Usage:
    bili login / logout / status / whoami
    bili video <BV号或URL> [--subtitle] [--ai] [--comments] [--related] [--yaml|--json]
    bili user <UID或用户名>          bili user-videos <UID> [--max N]
    bili search <关键词> [--type user|video] [--yaml|--json]
    bili hot / rank / feed / my-dynamics / following / history / watch-later / favorites
    bili dynamic-post <TEXT> / dynamic-delete <动态ID>
    bili like / coin / triple <BV号> / unfollow <UID>
    bili audio <BV号> [--segment N] [--no-split] [-o DIR]
"""

from __future__ import annotations

import click

from . import __version__
from .commands import account, audio, collections, common, discovery, interactions, user_search, video


# Keep helper names for backward compatibility with tests/importers.
def _format_duration(seconds: int) -> str:
    return common.format_duration(seconds)


def _format_count(n: int) -> str:
    return common.format_count(n)


@click.group()
@click.version_option(version=__version__, prog_name="bili")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool):
    """bili — Bilibili CLI tool 📺"""
    common.setup_logging(verbose)


# Register commands.
cli.add_command(account.login)
cli.add_command(account.logout)
cli.add_command(account.status)
cli.add_command(account.whoami)

cli.add_command(video.video)

cli.add_command(user_search.user)
cli.add_command(user_search.user_videos)
cli.add_command(user_search.search)

cli.add_command(collections.favorites)
cli.add_command(collections.following)
cli.add_command(collections.history)
cli.add_command(collections.watch_later)
cli.add_command(collections.feed)
cli.add_command(collections.my_dynamics)
cli.add_command(collections.dynamic_post)
cli.add_command(collections.dynamic_delete)

cli.add_command(discovery.hot_cmd)
cli.add_command(discovery.rank_cmd)

cli.add_command(interactions.like)
cli.add_command(interactions.coin)
cli.add_command(interactions.triple)
cli.add_command(interactions.unfollow)

cli.add_command(audio.audio)


if __name__ == "__main__":
    cli()
