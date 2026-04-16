"""Shared test fixtures."""

import os

import pytest
from bilibili_api.utils.network import Credential

os.environ.setdefault("OUTPUT", "rich")


@pytest.fixture
def mock_credential():
    """A fake credential for testing."""
    return Credential(sessdata="test_sessdata", bili_jct="test_bili_jct")


@pytest.fixture
def mock_video_info():
    """Sample video info response."""
    return {
        "bvid": "BV1test123",
        "title": "测试视频标题",
        "aid": 12345,
        "duration": 125,
        "desc": "这是一个测试视频",
        "owner": {"mid": 946974, "name": "TestUP"},
        "stat": {
            "view": 15000,
            "danmaku": 200,
            "like": 1200,
            "coin": 300,
            "favorite": 500,
            "share": 100,
        },
    }


@pytest.fixture
def mock_user_info():
    """Sample user info response."""
    return {
        "mid": 946974,
        "name": "TestUP",
        "level": 6,
        "sign": "这是签名",
        "coins": 2000,
        "vip": {"type": 2, "status": 1},
    }


@pytest.fixture
def mock_relation_info():
    """Sample user relation info response."""
    return {
        "mid": 946974,
        "following": 100,
        "follower": 50000,
    }
