"""Tests for CLI commands using Click CliRunner."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from bili_cli.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def _load_yaml(text: str):
    return yaml.safe_load(text)


# ===== Login/Status =====


def test_status_not_logged_in(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["status"])
        assert "未登录" in result.output
        assert result.exit_code != 0


def test_status_logged_in(runner, mock_user_info):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value=mock_user_info):
        result = runner.invoke(cli, ["status"])
        assert "TestUP" in result.output
        assert "✅" in result.output


def test_status_auto_yaml_when_stdout_is_not_tty(runner, mock_user_info, monkeypatch):
    monkeypatch.setenv("OUTPUT", "auto")
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value=mock_user_info):
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        data = _load_yaml(result.output)
        assert data["ok"] is True
        assert data["schema_version"] == "1"
        assert data["data"]["authenticated"] is True
        assert data["data"]["user"]["name"] == "TestUP"


def test_logout(runner):
    with patch("bili_cli.commands.common.clear_credential") as mock_clear:
        result = runner.invoke(cli, ["logout"])
        assert "已注销" in result.output
        mock_clear.assert_called_once()


def test_login_runtime_error(runner):
    with patch("bili_cli.commands.common.qr_login", new_callable=AsyncMock, side_effect=RuntimeError("二维码已过期")):
        result = runner.invoke(cli, ["login"])
        assert result.exit_code != 0
        assert "二维码已过期" in result.output


def test_login_unexpected_error_shows_friendly_message(runner):
    with patch("bili_cli.commands.common.qr_login", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["login"])
        assert result.exit_code != 0
        assert "登录失败: boom" in result.output


def test_whoami_not_logged_in(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["whoami"])
        assert result.exit_code != 0
        assert "未登录" in result.output


def test_user_not_found_yaml_error(runner):
    with patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=[]):
        result = runner.invoke(cli, ["user", "unknown-user", "--yaml"])
        assert result.exit_code != 0
        data = _load_yaml(result.output)
        assert data["ok"] is False
        assert data["error"]["code"] == "not_found"


def test_whoami_json(runner, mock_user_info, mock_relation_info):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value=mock_user_info), \
         patch("bili_cli.client.get_user_relation_info", new_callable=AsyncMock, return_value=mock_relation_info):
        result = runner.invoke(cli, ["whoami", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["schema_version"] == "1"
        assert data["data"]["user"]["name"] == "TestUP"
        assert data["data"]["relation"]["follower"] == 50000


def test_whoami_yaml(runner, mock_user_info, mock_relation_info):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value=mock_user_info), \
         patch("bili_cli.client.get_user_relation_info", new_callable=AsyncMock, return_value=mock_relation_info):
        result = runner.invoke(cli, ["whoami", "--yaml"])
        assert result.exit_code == 0
        data = _load_yaml(result.output)
        assert data["ok"] is True
        assert data["schema_version"] == "1"
        assert data["data"]["user"]["name"] == "TestUP"
        assert data["data"]["relation"]["follower"] == 50000


# ===== Video =====


def test_video_json(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info):
        result = runner.invoke(cli, ["video", "BV1test123", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["video"]["title"] == "测试视频标题"
        assert data["subtitle"]["available"] is False
        assert data["warnings"] == []


def test_video_yaml(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info):
        result = runner.invoke(cli, ["video", "BV1test123", "--yaml"])
        assert result.exit_code == 0
        data = _load_yaml(result.output)["data"]
        assert data["video"]["title"] == "测试视频标题"
        assert data["subtitle"]["available"] is False


def test_video_display(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info):
        result = runner.invoke(cli, ["video", "BV1test123"])
        assert result.exit_code == 0
        assert "测试视频标题" in result.output
        assert "BV1test123" in result.output


def test_video_does_not_load_optional_credential_when_no_optional_section(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None) as mock_get_cred, \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info) as mock_get_info:
        result = runner.invoke(cli, ["video", "BV1test123"])
        assert result.exit_code == 0
        mock_get_cred.assert_not_called()
        mock_get_info.assert_awaited_once_with("BV1test123", credential=None)


def test_video_uses_optional_credential_mode_when_needed(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None) as mock_get_cred, \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_video_subtitle", new_callable=AsyncMock, return_value=("sub", [])):
        result = runner.invoke(cli, ["video", "BV1test123", "--subtitle"])
        assert result.exit_code == 0
        mock_get_cred.assert_called_once_with(mode="optional")


def test_video_subtitle_timeline_uses_optional_credential_mode_when_needed(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None) as mock_get_cred, \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_video_subtitle", new_callable=AsyncMock, return_value=("sub", [])):
        result = runner.invoke(cli, ["video", "BV1test123", "--subtitle-timeline"])
        assert result.exit_code == 0
        mock_get_cred.assert_called_once_with(mode="optional")


def test_video_subtitle_timeline_prints_timeline_output(runner, mock_video_info):
    raw = [{"content": "Hello", "from": 0.0, "to": 2.5}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_video_subtitle", new_callable=AsyncMock, return_value=("Hello", raw)):
        result = runner.invoke(cli, ["video", "BV1test123", "--subtitle-timeline"])
        assert result.exit_code == 0
        assert "[00:00.000 --> 00:02.500] Hello" in result.output


def test_video_subtitle_timeline_supports_srt_output(runner, mock_video_info):
    raw = [{"content": "Hello", "from": 0.0, "to": 2.5}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_video_subtitle", new_callable=AsyncMock, return_value=("Hello", raw)):
        result = runner.invoke(cli, ["video", "BV1test123", "--subtitle-timeline", "--subtitle-format", "srt"])
        assert result.exit_code == 0
        assert "00:00:00,000 --> 00:00:02,500" in result.output


def test_video_structured_output_includes_requested_extras(runner, mock_video_info):
    raw = [{"content": "Hello", "from": 0.0, "to": 2.5}]
    comments = [{"rpid": 1, "member": {"mid": 2, "uname": "TestUser"}, "content": {"message": "Nice!"}, "like": 3}]
    related = [{"bvid": "BV1rel", "title": "Related Video", "owner": {"name": "UP"}}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_video_subtitle", new_callable=AsyncMock, return_value=("Hello", raw)), \
         patch(
             "bili_cli.client.get_video_ai_conclusion",
             new_callable=AsyncMock,
             return_value={"model_result": {"summary": "AI summary"}},
         ), \
         patch("bili_cli.client.get_video_comments", new_callable=AsyncMock, return_value={"replies": comments}), \
         patch("bili_cli.client.get_related_videos", new_callable=AsyncMock, return_value=related):
        result = runner.invoke(
            cli,
            ["video", "BV1test123", "--subtitle-timeline", "--ai", "--comments", "--related", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["video"]["bvid"] == "BV1test123"
        assert data["subtitle"]["available"] is True
        assert data["subtitle"]["items"][0]["content"] == "Hello"
        assert data["ai_summary"] == "AI summary"
        assert data["comments"][0]["author"]["name"] == "TestUser"
        assert data["related"][0]["bvid"] == "BV1rel"


def test_video_subtitle_error_is_nonfatal(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info), \
         patch("bili_cli.client.get_video_subtitle", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["video", "BV1test123", "--subtitle"])
        assert result.exit_code == 0
        assert "获取字幕失败" in result.output


def test_video_invalid_bvid(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["video", "invalid"])
        assert result.exit_code != 0


def test_video_api_error_returns_nonzero(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["video", "BV1test123"])
        assert result.exit_code != 0
        assert "获取视频信息失败" in result.output


# ===== Hot =====


def test_hot_command(runner):
    mock_data = {
        "list": [
            {
                "bvid": "BV1hot",
                "title": "热门视频",
                "owner": {"name": "HotUP"},
                "stat": {"view": 100000, "like": 5000},
            }
        ]
    }
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, return_value=mock_data):
        result = runner.invoke(cli, ["hot", "--max", "1"])
        assert result.exit_code == 0
        assert "BV1hot" in result.output
        assert "热门" in result.output


def test_hot_forwards_page_option(runner):
    mock_data = {"list": []}
    with patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, return_value=mock_data) as mock_hot:
        result = runner.invoke(cli, ["hot", "--page", "2", "--max", "5"])
        assert result.exit_code == 0
        mock_hot.assert_awaited_once_with(pn=2, ps=5)


def test_hot_json(runner):
    mock_data = {"list": [{"bvid": "BV1hot", "title": "Hot"}]}
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, return_value=mock_data):
        result = runner.invoke(cli, ["hot", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["items"][0]["bvid"] == "BV1hot"


def test_hot_yaml(runner):
    mock_data = {"list": [{"bvid": "BV1hot", "title": "Hot"}]}
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, return_value=mock_data):
        result = runner.invoke(cli, ["hot", "--yaml"])
        assert result.exit_code == 0
        data = _load_yaml(result.output)["data"]
        assert data["items"][0]["bvid"] == "BV1hot"


def test_hot_invalid_max(runner):
    result = runner.invoke(cli, ["hot", "--max", "0"])
    assert result.exit_code != 0


def test_hot_invalid_page(runner):
    result = runner.invoke(cli, ["hot", "--page", "0"])
    assert result.exit_code != 0


def test_hot_api_error_returns_nonzero(runner):
    with patch("bili_cli.client.get_hot_videos", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["hot"])
        assert result.exit_code != 0
        assert "获取热门视频失败" in result.output


def test_rank_json(runner):
    mock_data = {"list": [{"bvid": "BV1rank", "title": "Rank"}]}
    with patch("bili_cli.client.get_rank_videos", new_callable=AsyncMock, return_value=mock_data):
        result = runner.invoke(cli, ["rank", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["items"][0]["bvid"] == "BV1rank"


def test_structured_output_flags_are_mutually_exclusive(runner, mock_video_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.extract_bvid", return_value="BV1test123"), \
         patch("bili_cli.client.get_video_info", new_callable=AsyncMock, return_value=mock_video_info):
        result = runner.invoke(cli, ["video", "BV1test123", "--json", "--yaml"])
        assert result.exit_code != 0
        assert "不能同时使用 --json 和 --yaml" in result.output


def test_rank_api_error_returns_nonzero(runner):
    with patch("bili_cli.client.get_rank_videos", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["rank"])
        assert result.exit_code != 0
        assert "获取排行榜失败" in result.output


def test_rank_forwards_day_option(runner):
    mock_data = {"list": []}
    with patch("bili_cli.client.get_rank_videos", new_callable=AsyncMock, return_value=mock_data) as mock_rank:
        result = runner.invoke(cli, ["rank", "--day", "7"])
        assert result.exit_code == 0
        mock_rank.assert_awaited_once_with(day=7)


def test_rank_invalid_max(runner):
    result = runner.invoke(cli, ["rank", "--max", "0"])
    assert result.exit_code != 0


# ===== Search =====


def test_search_user(runner):
    mock_results = [{"mid": 123, "uname": "TestUser", "fans": 1000, "videos": 10, "usign": "Hi"}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=mock_results):
        result = runner.invoke(cli, ["search", "test"])
        assert result.exit_code == 0
        assert "TestUser" in result.output


def test_search_video(runner):
    mock_results = [{"bvid": "BV1found", "title": "Found Video", "author": "UP", "play": 5000, "duration": "10:30"}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.search_video", new_callable=AsyncMock, return_value=mock_results):
        result = runner.invoke(cli, ["search", "test", "--type", "video"])
        assert result.exit_code == 0
        assert "BV1found" in result.output


def test_search_video_filters_items_without_bvid(runner):
    mock_results = [
        {"bvid": "", "title": "No BV", "author": "UP", "play": 1, "duration": "1:00"},
        {"bvid": "BV1found", "title": "Found Video", "author": "UP", "play": 5000, "duration": "10:30"},
    ]
    with patch("bili_cli.client.search_video", new_callable=AsyncMock, return_value=mock_results):
        result = runner.invoke(cli, ["search", "test", "--type", "video"])
        assert result.exit_code == 0
        assert "BV1found" in result.output
        assert "No BV" not in result.output


def test_search_forwards_page_for_user(runner):
    with patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=[]) as mock_search_user:
        result = runner.invoke(cli, ["search", "test", "--page", "3"])
        assert result.exit_code == 0
        mock_search_user.assert_awaited_once_with("test", page=3)


def test_search_forwards_page_for_video(runner):
    with patch("bili_cli.client.search_video", new_callable=AsyncMock, return_value=[]) as mock_search_video:
        result = runner.invoke(cli, ["search", "test", "--type", "video", "--page", "2"])
        assert result.exit_code == 0
        mock_search_video.assert_awaited_once_with("test", page=2)


def test_search_invalid_page(runner):
    result = runner.invoke(cli, ["search", "test", "--page", "0"])
    assert result.exit_code != 0


def test_search_invalid_max(runner):
    result = runner.invoke(cli, ["search", "test", "--max", "0"])
    assert result.exit_code != 0


def test_search_empty(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=[]):
        result = runner.invoke(cli, ["search", "nonexistent_xyz"])
        assert "未找到" in result.output


def test_search_user_api_error_returns_nonzero(runner):
    with patch("bili_cli.client.search_user", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["search", "abc"])
        assert result.exit_code != 0
        assert "搜索用户失败" in result.output


def test_search_video_api_error_returns_nonzero(runner):
    with patch("bili_cli.client.search_video", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["search", "abc", "--type", "video"])
        assert result.exit_code != 0
        assert "搜索视频失败" in result.output


# ===== User =====


def test_user_by_uid(runner, mock_user_info, mock_relation_info):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_user_info", new_callable=AsyncMock, return_value=mock_user_info), \
         patch("bili_cli.client.get_user_relation_info", new_callable=AsyncMock, return_value=mock_relation_info):
        result = runner.invoke(cli, ["user", "946974"])
        assert result.exit_code == 0
        assert "TestUP" in result.output
        assert "5.0万" in result.output  # follower count


def test_user_videos_json(runner):
    videos = [{"bvid": "BV1new", "title": "New Video", "play": 123, "length": "01:23"}]
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_user_videos", new_callable=AsyncMock, return_value=videos):
        result = runner.invoke(cli, ["user-videos", "946974", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data[0]["bvid"] == "BV1new"


def test_user_videos_invalid_max(runner):
    result = runner.invoke(cli, ["user-videos", "946974", "--max", "0"])
    assert result.exit_code != 0


def test_user_videos_api_error_returns_nonzero(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None), \
         patch("bili_cli.client.get_user_videos", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["user-videos", "946974"])
        assert result.exit_code != 0
        assert "获取视频列表失败" in result.output


def test_user_videos_handles_invalid_length_field(runner):
    videos = [{"bvid": "BV1new", "title": "New Video", "play": 123, "length": "abc"}]
    with patch("bili_cli.client.get_user_videos", new_callable=AsyncMock, return_value=videos):
        result = runner.invoke(cli, ["user-videos", "946974"])
        assert result.exit_code == 0
        assert "00:00" in result.output


def test_user_by_name_with_missing_uid_returns_nonzero(runner):
    with patch("bili_cli.client.search_user", new_callable=AsyncMock, return_value=[{"uname": "TestUser"}]):
        result = runner.invoke(cli, ["user", "testuser"])
        assert result.exit_code != 0
        assert "缺少 UID" in result.output


# ===== Collections =====


def test_favorites_list_success(runner):
    mock_cred = MagicMock()
    favs = [{"id": 100, "title": "默认收藏夹", "media_count": 8}]
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_favorite_list", new_callable=AsyncMock, return_value=favs):
        result = runner.invoke(cli, ["favorites"])
        assert result.exit_code == 0
        assert "默认收藏夹" in result.output
        assert "100" in result.output


def test_favorites_detail_success(runner):
    mock_cred = MagicMock()
    data = {
        "medias": [{"bvid": "BV1fav", "title": "Fav Video", "upper": {"name": "FavUP"}, "duration": 120}],
        "has_more": True,
    }
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_favorite_videos", new_callable=AsyncMock, return_value=data):
        result = runner.invoke(cli, ["favorites", "100", "--page", "2"])
        assert result.exit_code == 0
        assert "BV1fav" in result.output
        assert "favorites 100 --page 3" in result.output


def test_favorites_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["favorites"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_favorites_invalid_page(runner):
    result = runner.invoke(cli, ["favorites", "123", "--page", "0"])
    assert result.exit_code != 0


def test_favorites_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_favorite_list", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["favorites"])
        assert result.exit_code != 0
        assert "获取收藏夹列表失败" in result.output


def test_following_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["following"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_following_success(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value={"mid": 946974}), \
         patch(
             "bili_cli.client.get_followings",
             new_callable=AsyncMock,
             return_value={"list": [{"mid": 1, "uname": "UPA", "sign": "hello"}], "total": 1},
         ):
        result = runner.invoke(cli, ["following"])
        assert result.exit_code == 0
        assert "UPA" in result.output
        assert "following --page 2" in result.output


def test_following_invalid_page(runner):
    result = runner.invoke(cli, ["following", "--page", "0"])
    assert result.exit_code != 0


def test_following_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["following"])
        assert result.exit_code != 0
        assert "获取关注列表失败" in result.output


def test_history_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["history"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_history_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_watch_history", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["history"])
        assert result.exit_code != 0
        assert "获取观看历史失败" in result.output


def test_history_forwards_page_and_max(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_watch_history", new_callable=AsyncMock, return_value={"list": []}) as mock_history:
        result = runner.invoke(cli, ["history", "--page", "2", "--max", "40"])
        assert result.exit_code == 0
        mock_history.assert_awaited_once_with(page=2, count=40, credential=mock_cred)


def test_history_invalid_page(runner):
    result = runner.invoke(cli, ["history", "--page", "0"])
    assert result.exit_code != 0


def test_history_invalid_max(runner):
    result = runner.invoke(cli, ["history", "--max", "101"])
    assert result.exit_code != 0


def test_watch_later_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["watch-later"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_watch_later_success(runner):
    mock_cred = MagicMock()
    data = {"list": [{"bvid": "BV1later", "title": "Later", "owner": {"name": "UP"}, "duration": 60}], "count": 1}
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_toview", new_callable=AsyncMock, return_value=data):
        result = runner.invoke(cli, ["watch-later"])
        assert result.exit_code == 0
        assert "BV1later" in result.output


def test_watch_later_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_toview", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["watch-later"])
        assert result.exit_code != 0
        assert "获取稍后再看失败" in result.output


def test_feed_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["feed"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_feed_success(runner):
    mock_cred = MagicMock()
    feed_data = {
        "items": [
            {
                "modules": {
                    "module_author": {"name": "UPA", "pub_time": "今天"},
                    "module_dynamic": {"desc": {"text": "动态正文"}, "major": {"archive": {"title": "视频标题"}}},
                    "module_stat": {"comment": {"count": 2}, "like": {"count": 3}},
                }
            }
        ],
        "next_offset": 12345,
    }
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_dynamic_feed", new_callable=AsyncMock, return_value=feed_data):
        result = runner.invoke(cli, ["feed"])
        assert result.exit_code == 0
        assert "UPA" in result.output
        assert "视频标题" in result.output
        assert "bili feed --offset 12345" in result.output


def test_feed_api_error_returns_nonzero(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_dynamic_feed", new_callable=AsyncMock, side_effect=Exception("api down")):
        result = runner.invoke(cli, ["feed"])
        assert result.exit_code != 0
        assert "获取动态失败" in result.output


def test_feed_forwards_offset(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_dynamic_feed", new_callable=AsyncMock, return_value={"items": []}) as mock_feed:
        result = runner.invoke(cli, ["feed", "--offset", "123"])
        assert result.exit_code == 0
        mock_feed.assert_awaited_once_with(offset="123", credential=mock_cred)


def test_my_dynamics_success(runner):
    mock_cred = MagicMock()
    data = {
        "cards": [
            {
                "desc": {"dynamic_id": 123, "timestamp": 1700000000},
                "card": json.dumps({"item": {"content": "测试动态内容"}}),
            }
        ],
        "next_offset": 456,
    }
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value={"mid": 946974}), \
         patch("bili_cli.client.get_user_dynamics", new_callable=AsyncMock, return_value=data):
        result = runner.invoke(cli, ["my-dynamics", "--max", "1"])
        assert result.exit_code == 0
        assert "123" in result.output
        assert "测试动态内容" in result.output
        assert "my-dynamics --offset 456" in result.output


def test_my_dynamics_forwards_options(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.get_self_info", new_callable=AsyncMock, return_value={"mid": 946974}), \
         patch("bili_cli.client.get_user_dynamics", new_callable=AsyncMock, return_value={"cards": []}) as mock_get:
        result = runner.invoke(cli, ["my-dynamics", "--offset", "99", "--top"])
        assert result.exit_code == 0
        mock_get.assert_awaited_once_with(uid=946974, offset=99, need_top=True, credential=mock_cred)


def test_dynamic_post_text_success(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.post_text_dynamic", new_callable=AsyncMock, return_value={"dynamic_id": 1001}) as mock_post:
        result = runner.invoke(cli, ["dynamic-post", "hello dynamic"])
        assert result.exit_code == 0
        assert "1001" in result.output
        mock_post.assert_awaited_once_with("hello dynamic", credential=mock_cred)


def test_dynamic_post_from_file_success(runner):
    mock_cred = MagicMock()
    with runner.isolated_filesystem():
        with open("dyn.txt", "w", encoding="utf-8") as f:
            f.write("from file dynamic")
        with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
             patch("bili_cli.client.post_text_dynamic", new_callable=AsyncMock, return_value={}) as mock_post:
            result = runner.invoke(cli, ["dynamic-post", "--from-file", "dyn.txt"])
            assert result.exit_code == 0
            mock_post.assert_awaited_once_with("from file dynamic", credential=mock_cred)


def test_dynamic_delete_yes_calls_client(runner):
    mock_cred = MagicMock()
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.delete_dynamic", new_callable=AsyncMock, return_value={}) as mock_delete:
        result = runner.invoke(cli, ["dynamic-delete", "123", "--yes"])
        assert result.exit_code == 0
        mock_delete.assert_awaited_once_with(dynamic_id=123, credential=mock_cred)


# ===== Interactions =====


def test_like_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["like", "BV1test"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_coin_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["coin", "BV1test"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_triple_requires_login(runner):
    with patch("bili_cli.commands.common.get_credential", return_value=None):
        result = runner.invoke(cli, ["triple", "BV1test"])
        assert result.exit_code != 0
        assert "需要登录" in result.output


def test_unfollow_yes_calls_client(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.unfollow_user", new_callable=AsyncMock, return_value={}) as mock_unfollow:
        result = runner.invoke(cli, ["unfollow", "946974", "--yes"])
        assert result.exit_code == 0
        mock_unfollow.assert_awaited_once_with(uid=946974, credential=mock_cred)


def test_like_json_output(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.like_video", new_callable=AsyncMock, return_value={}):
        result = runner.invoke(cli, ["like", "BV1ok", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["action"] == "like"
        assert data["bvid"] == "BV1ok"


def test_coin_yaml_output(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.coin_video", new_callable=AsyncMock, return_value={}):
        result = runner.invoke(cli, ["coin", "BV1ok", "--num", "2", "--yaml"])
        assert result.exit_code == 0
        data = _load_yaml(result.output)["data"]
        assert data["action"] == "coin"
        assert data["coins"] == 2


def test_triple_json_output(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.triple_video", new_callable=AsyncMock, return_value={"like": True, "coin": True, "fav": True}):
        result = runner.invoke(cli, ["triple", "BV1ok", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["action"] == "triple"
        assert data["result"]["favorite"] is True


def test_coin_invalid_num(runner):
    result = runner.invoke(cli, ["coin", "BV1test", "--num", "3"])
    assert result.exit_code != 0


def test_like_requires_write_credential(runner):
    mock_cred = MagicMock()
    mock_cred.sessdata = "valid_sess"
    mock_cred.bili_jct = ""
    with patch(
        "bili_cli.commands.common.get_credential",
        side_effect=lambda mode="read": None if mode == "write" else mock_cred,
    ):
        result = runner.invoke(cli, ["like", "BV1test"])
        assert result.exit_code != 0
        assert "缺少 bili_jct" in result.output


@pytest.mark.parametrize("cmd", ["like", "coin", "triple"])
def test_interaction_invalid_bvid_returns_nonzero(runner, cmd):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", side_effect=ValueError("bad bvid")):
        result = runner.invoke(cli, [cmd, "invalid"])
        assert result.exit_code != 0
        assert "bad bvid" in result.output


def test_like_failure_returns_nonzero(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.like_video", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["like", "BV1ok"])
        assert result.exit_code != 0
        assert "操作失败" in result.output


def test_coin_failure_returns_nonzero(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.coin_video", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["coin", "BV1ok"])
        assert result.exit_code != 0
        assert "投币失败" in result.output


def test_triple_failure_returns_nonzero(runner):
    mock_cred = MagicMock()
    mock_cred.bili_jct = "valid_jct"
    with patch("bili_cli.commands.common.get_credential", return_value=mock_cred), \
         patch("bili_cli.client.extract_bvid", return_value="BV1ok"), \
         patch("bili_cli.client.triple_video", new_callable=AsyncMock, side_effect=Exception("boom")):
        result = runner.invoke(cli, ["triple", "BV1ok"])
        assert result.exit_code != 0
        assert "三连失败" in result.output


# ===== Version =====


def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "bili" in result.output
