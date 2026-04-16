"""Tests for auth module."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bilibili_api.exceptions import NetworkException
from bilibili_api.utils.network import Credential

from bili_cli.auth import (
    _extract_browser_credential,
    _get_qr_terminal_output,
    _load_saved_credential,
    _render_compact_qr,
    _supports_unicode_half_blocks,
    _validate_credential,
    clear_credential,
    get_credential,
    save_credential,
)


def test_load_missing_file(tmp_path):
    with patch("bili_cli.auth.CREDENTIAL_FILE", tmp_path / "nope.json"):
        assert _load_saved_credential() is None


def test_save_and_load(tmp_path):
    cred_file = tmp_path / "cred.json"
    with patch("bili_cli.auth.CREDENTIAL_FILE", cred_file), \
         patch("bili_cli.auth.CONFIG_DIR", tmp_path):
        cred = Credential(
            sessdata="test_sess", bili_jct="test_jct",
            buvid3="buvid3_val", buvid4="buvid4_val", dedeuserid="12345",
        )
        save_credential(cred)

        # File should exist with correct permissions
        assert cred_file.exists()

        # Load it back
        loaded = _load_saved_credential()
        assert loaded is not None
        assert loaded.sessdata == "test_sess"
        assert loaded.bili_jct == "test_jct"
        assert loaded.buvid3 == "buvid3_val"
        assert loaded.buvid4 == "buvid4_val"
        assert loaded.dedeuserid == "12345"


def test_save_creates_directory(tmp_path):
    new_dir = tmp_path / "new_config"
    cred_file = new_dir / "cred.json"
    with patch("bili_cli.auth.CREDENTIAL_FILE", cred_file), \
         patch("bili_cli.auth.CONFIG_DIR", new_dir):
        cred = Credential(sessdata="s", bili_jct="j")
        save_credential(cred)
        assert new_dir.exists()
        assert cred_file.exists()


def test_load_corrupt_file(tmp_path):
    cred_file = tmp_path / "bad.json"
    cred_file.write_text("not json at all")
    with patch("bili_cli.auth.CREDENTIAL_FILE", cred_file):
        assert _load_saved_credential() is None


def test_load_empty_sessdata(tmp_path):
    cred_file = tmp_path / "empty.json"
    cred_file.write_text(json.dumps({"sessdata": "", "bili_jct": "x"}))
    with patch("bili_cli.auth.CREDENTIAL_FILE", cred_file):
        assert _load_saved_credential() is None


def test_clear_credential(tmp_path):
    cred_file = tmp_path / "cred.json"
    cred_file.write_text("{}")
    with patch("bili_cli.auth.CREDENTIAL_FILE", cred_file):
        clear_credential()
        assert not cred_file.exists()


def test_clear_credential_nonexistent(tmp_path):
    with patch("bili_cli.auth.CREDENTIAL_FILE", tmp_path / "nope.json"):
        # Should not raise
        clear_credential()


def test_validate_valid_credential():
    with patch("bilibili_api.user.get_self_info", new_callable=AsyncMock, return_value={"mid": 1}):
        cred = Credential(sessdata="valid")
        assert _validate_credential(cred) is True


def test_validate_expired_credential():
    with patch("bilibili_api.user.get_self_info", new_callable=AsyncMock, side_effect=Exception("expired")):
        cred = Credential(sessdata="expired")
        assert _validate_credential(cred) is False


def test_validate_network_error_returns_none():
    with patch("bilibili_api.user.get_self_info", new_callable=AsyncMock, side_effect=NetworkException(-1, "timeout")):
        cred = Credential(sessdata="valid")
        assert _validate_credential(cred) is None


def test_validate_credential_requires_bili_jct_for_write():
    with patch("bilibili_api.user.get_self_info", new_callable=AsyncMock, return_value={"mid": 1}):
        cred = Credential(sessdata="valid", bili_jct="")
        assert _validate_credential(cred, require_write=True) is False


def test_get_credential_uses_saved_when_valid():
    saved = Credential(sessdata="saved", bili_jct="jct")
    with patch("bili_cli.auth._load_saved_credential", return_value=saved), \
         patch("bili_cli.auth._validate_credential", return_value=True) as mock_validate, \
         patch("bili_cli.auth._extract_browser_credential") as mock_extract:
        cred = get_credential()
        assert cred is saved
        mock_validate.assert_called_once_with(saved, require_write=False)
        mock_extract.assert_not_called()


def test_get_credential_falls_back_to_browser_and_saves():
    browser = Credential(sessdata="browser", bili_jct="jct")
    with patch("bili_cli.auth._load_saved_credential", return_value=None), \
         patch("bili_cli.auth._extract_browser_credential", return_value=browser), \
         patch("bili_cli.auth._validate_credential", return_value=True), \
         patch("bili_cli.auth.save_credential") as mock_save:
        cred = get_credential()
        assert cred is browser
        mock_save.assert_called_once_with(browser)


def test_get_credential_keeps_saved_on_validation_network_error():
    saved = Credential(sessdata="saved", bili_jct="jct")
    with patch("bili_cli.auth._load_saved_credential", return_value=saved), \
         patch("bili_cli.auth._validate_credential", return_value=None), \
         patch("bili_cli.auth.clear_credential") as mock_clear, \
         patch("bili_cli.auth._extract_browser_credential") as mock_extract:
        cred = get_credential()
        assert cred is saved
        mock_clear.assert_not_called()
        mock_extract.assert_not_called()


def test_get_credential_clears_expired_saved_and_returns_none_when_browser_invalid():
    saved = Credential(sessdata="saved", bili_jct="jct")
    browser = Credential(sessdata="browser", bili_jct="jct")
    with patch("bili_cli.auth._load_saved_credential", return_value=saved), \
         patch("bili_cli.auth._extract_browser_credential", return_value=browser), \
         patch("bili_cli.auth._validate_credential", side_effect=[False, False]), \
         patch("bili_cli.auth.clear_credential") as mock_clear, \
         patch("bili_cli.auth.save_credential") as mock_save:
        cred = get_credential()
        assert cred is None
        mock_clear.assert_called_once()
        mock_save.assert_not_called()


def test_get_credential_optional_uses_saved_without_validation():
    saved = Credential(sessdata="saved", bili_jct="jct")
    with patch("bili_cli.auth._load_saved_credential", return_value=saved), \
         patch("bili_cli.auth._validate_credential") as mock_validate, \
         patch("bili_cli.auth._extract_browser_credential") as mock_extract:
        cred = get_credential(mode="optional")
        assert cred is saved
        mock_validate.assert_not_called()
        mock_extract.assert_not_called()


def test_get_credential_write_rejects_missing_bili_jct():
    saved = Credential(sessdata="saved", bili_jct="")
    with patch("bili_cli.auth._load_saved_credential", return_value=saved), \
         patch("bili_cli.auth._extract_browser_credential", return_value=None), \
         patch("bili_cli.auth._validate_credential", return_value=False):
        cred = get_credential(mode="write")
        assert cred is None


def test_extract_browser_credential_timeout_returns_none():
    with patch("bili_cli.auth.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
        assert _extract_browser_credential() is None


def test_extract_browser_credential_bad_json_returns_none():
    fake = SimpleNamespace(returncode=0, stdout="not-json", stderr="")
    with patch("bili_cli.auth.subprocess.run", return_value=fake):
        assert _extract_browser_credential() is None


def test_extract_browser_credential_empty_output_returns_none():
    fake = SimpleNamespace(returncode=0, stdout="   ", stderr="")
    with patch("bili_cli.auth.subprocess.run", return_value=fake):
        assert _extract_browser_credential() is None


def test_render_compact_qr_returns_multiline_text():
    with patch("bili_cli.auth.shutil.get_terminal_size", return_value=SimpleNamespace(columns=200, lines=24)):
        rendered = _render_compact_qr("https://example.com")
    assert rendered is not None
    assert "\n" in rendered
    assert any(ch in rendered for ch in "▀▄█")


def test_render_compact_qr_returns_none_when_terminal_too_narrow():
    with patch("bili_cli.auth.shutil.get_terminal_size", return_value=SimpleNamespace(columns=1, lines=24)):
        assert _render_compact_qr("https://example.com") is None


def test_supports_unicode_half_blocks_with_utf8():
    with patch("bili_cli.auth.sys.stdout", SimpleNamespace(encoding="utf-8")):
        assert _supports_unicode_half_blocks() is True


def test_supports_unicode_half_blocks_with_non_unicode_encoding():
    with patch("bili_cli.auth.sys.stdout", SimpleNamespace(encoding="cp1252")):
        assert _supports_unicode_half_blocks() is False


def test_get_qr_terminal_output_falls_back_when_private_qr_link_missing():
    class DummyLogin:
        def get_qrcode_terminal(self):
            return "DEFAULT_QR"

    assert _get_qr_terminal_output(DummyLogin()) == "DEFAULT_QR"


def test_get_qr_terminal_output_falls_back_when_unicode_not_supported():
    class DummyLogin:
        _QrCodeLogin__qr_link = "https://example.com"

        def get_qrcode_terminal(self):
            return "DEFAULT_QR"

    with patch("bili_cli.auth._supports_unicode_half_blocks", return_value=False):
        assert _get_qr_terminal_output(DummyLogin()) == "DEFAULT_QR"


def test_get_qr_terminal_output_falls_back_when_compact_render_returns_none():
    class DummyLogin:
        _QrCodeLogin__qr_link = "https://example.com"

        def get_qrcode_terminal(self):
            return "DEFAULT_QR"

    with patch("bili_cli.auth._supports_unicode_half_blocks", return_value=True), \
         patch("bili_cli.auth._render_compact_qr", return_value=None):
        assert _get_qr_terminal_output(DummyLogin()) == "DEFAULT_QR"


def test_get_qr_terminal_output_prefers_compact_rendering_when_available():
    class DummyLogin:
        _QrCodeLogin__qr_link = "https://example.com"

        def get_qrcode_terminal(self):
            return "DEFAULT_QR"

    with patch("bili_cli.auth._supports_unicode_half_blocks", return_value=True), \
         patch("bili_cli.auth._render_compact_qr", return_value="COMPACT_QR"):
        assert _get_qr_terminal_output(DummyLogin()) == "COMPACT_QR"
