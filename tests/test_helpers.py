"""Tests for pure helper functions — no mocking needed."""

import pytest

from bili_cli.cli import _format_count, _format_duration
from bili_cli.client import extract_bvid
from bili_cli.exceptions import InvalidBvidError


class TestFormatCount:
    def test_zero(self):
        assert _format_count(0) == "0"

    def test_small(self):
        assert _format_count(999) == "999"

    def test_exactly_10000(self):
        assert _format_count(10000) == "1.0万"

    def test_wan(self):
        assert _format_count(15000) == "1.5万"

    def test_large(self):
        assert _format_count(15291000) == "1529.1万"

    def test_numeric_string(self):
        assert _format_count("12000") == "1.2万"

    def test_invalid_string(self):
        assert _format_count("abc") == "0"


class TestFormatDuration:
    def test_zero(self):
        assert _format_duration(0) == "00:00"

    def test_seconds_only(self):
        assert _format_duration(45) == "00:45"

    def test_minutes_and_seconds(self):
        assert _format_duration(125) == "02:05"

    def test_exact_minute(self):
        assert _format_duration(60) == "01:00"

    def test_hours(self):
        assert _format_duration(3661) == "1:01:01"

    def test_exact_hour(self):
        assert _format_duration(3600) == "1:00:00"

    def test_numeric_string(self):
        assert _format_duration("125") == "02:05"

    def test_invalid_string(self):
        assert _format_duration("abc") == "00:00"


class TestExtractBvid:
    def test_raw_bvid(self):
        assert extract_bvid("BV1ABcsztEcY") == "BV1ABcsztEcY"

    def test_full_url(self):
        assert extract_bvid("https://www.bilibili.com/video/BV1ABcsztEcY") == "BV1ABcsztEcY"

    def test_url_with_params(self):
        assert extract_bvid("https://www.bilibili.com/video/BV1ABcsztEcY?p=1&t=30") == "BV1ABcsztEcY"

    def test_mobile_url(self):
        assert extract_bvid("https://m.bilibili.com/video/BV1ABcsztEcY") == "BV1ABcsztEcY"

    def test_invalid_raises(self):
        with pytest.raises(InvalidBvidError, match="无法提取"):
            extract_bvid("not-a-bvid")

    def test_empty_raises(self):
        with pytest.raises(InvalidBvidError):
            extract_bvid("")

    def test_numeric_only_raises(self):
        with pytest.raises(InvalidBvidError):
            extract_bvid("12345678")

    def test_short_bvid_raises(self):
        with pytest.raises(InvalidBvidError):
            extract_bvid("BV123")
