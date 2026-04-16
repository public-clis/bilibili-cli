"""Tests for subtitle formatting helpers."""

from bili_cli.client import (
    _format_subtitle_srt_time,
    _format_subtitle_time,
    format_subtitle_timeline,
)


def test_format_subtitle_time_returns_minute_precision():
    assert _format_subtitle_time(65.333) == "01:05.333"


def test_format_subtitle_srt_time_returns_srt_format():
    assert _format_subtitle_srt_time(3665.789) == "01:01:05,789"


def test_format_subtitle_timeline_returns_empty_string_for_empty_input():
    assert format_subtitle_timeline([]) == ""
    assert format_subtitle_timeline(None) == ""


def test_format_subtitle_timeline_formats_timeline_output():
    raw = [
        {"content": "First", "from": 0.0, "to": 2.0},
        {"content": "Second", "from": 2.0, "to": 5.5},
    ]

    result = format_subtitle_timeline(raw)

    assert result.splitlines() == [
        "[00:00.000 --> 00:02.000] First",
        "[00:02.000 --> 00:05.500] Second",
    ]


def test_format_subtitle_timeline_formats_srt_output():
    raw = [
        {"content": "Hello", "from": 0.0, "to": 2.5},
        {"content": "World", "from": 2.5, "to": 5.0},
    ]

    result = format_subtitle_timeline(raw, output_format="srt")

    assert result.splitlines() == [
        "1",
        "00:00:00,000 --> 00:00:02,500",
        "Hello",
        "",
        "2",
        "00:00:02,500 --> 00:00:05,000",
        "World",
    ]
    assert result.endswith("\n")


def test_format_subtitle_timeline_handles_missing_fields():
    result = format_subtitle_timeline([{"content": "Test"}])

    assert result == "[00:00.000 --> 00:00.000] Test"
