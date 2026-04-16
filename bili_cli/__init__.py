"""bilibili-cli — browse Bilibili from the terminal."""

try:
    from importlib.metadata import version

    __version__ = version("bilibili-cli")
except Exception:
    __version__ = "0.0.0"
