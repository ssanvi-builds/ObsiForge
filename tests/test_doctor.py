"""Tests for obsiforge.doctor module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obsiforge.doctor import (
    _check_mcp_auth,
    _check_obsidian_running,
    _check_plugins_enabled,
    _check_port_in_use,
    _check_settings_json,
    _check_smart_env,
    _check_vault_files,
)


class TestCheckObsidianRunning:
    """Tests for _check_obsidian_running."""

    def test_obsidian_running(self):
        with patch("obsiforge.doctor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")
            result = _check_obsidian_running()
            assert result["running"] is True
            assert "12345" in result["pids"]

    def test_obsidian_not_running(self):
        with patch("obsiforge.doctor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = _check_obsidian_running()
            assert result["running"] is False


class TestCheckPortInUse:
    """Tests for _check_port_in_use."""

    def test_port_available(self):
        with patch("obsiforge.doctor.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1  # Connection refused
            mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _check_port_in_use(9999)
            assert result["in_use"] is False


class TestCheckPluginsEnabled:
    """Tests for _check_plugins_enabled."""

    def test_all_plugins_enabled(self, tmp_path):
        vault = tmp_path / "vault"
        obs_dir = vault / ".obsidian"
        obs_dir.mkdir(parents=True)
        plugins_file = obs_dir / "community-plugins.json"
        plugins_file.write_text(json.dumps([
            "mcp-tools-istefox",
            "smart-connections",
            "obsidian-local-rest-api",
        ]))
        result = _check_plugins_enabled(str(vault))
        assert result["missing"] == set()
        assert "3/3" in result["details"]

    def test_missing_plugins(self, tmp_path):
        vault = tmp_path / "vault"
        obs_dir = vault / ".obsidian"
        obs_dir.mkdir(parents=True)
        plugins_file = obs_dir / "community-plugins.json"
        plugins_file.write_text(json.dumps(["mcp-tools-istefox"]))
        result = _check_plugins_enabled(str(vault))
        assert "smart-connections" in result["missing"]
        assert "obsidian-local-rest-api" in result["missing"]

    def test_no_plugins_file(self, tmp_path):
        vault = tmp_path / "vault"
        result = _check_plugins_enabled(str(vault))
        assert result["missing"] == {"mcp-tools-istefox", "smart-connections", "obsidian-local-rest-api"}


class TestCheckSmartEnv:
    """Tests for _check_smart_env."""

    def test_indexed_vault(self, tmp_path):
        vault = tmp_path / "vault"
        smart_env = vault / ".smart-env" / "multi"
        smart_env.mkdir(parents=True)
        (smart_env / "note1.ajson").write_text("smart_sources: {}")
        (smart_env / "note2.ajson").write_text("smart_sources: {}")
        result = _check_smart_env(str(vault))
        assert result["indexed"] is True
        assert "2 source files" in result["details"]

    def test_no_smart_env(self, tmp_path):
        vault = tmp_path / "vault"
        result = _check_smart_env(str(vault))
        assert result["indexed"] is False


class TestCheckVaultFiles:
    """Tests for _check_vault_files."""

    def test_all_files_present(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "CLAUDE.md").write_text("# Vault")
        claude_dir = vault / "Claude"
        claude_dir.mkdir()
        (claude_dir / "MEMORY.md").write_text("# Memory")
        (vault / ".mcp.json").write_text("{}")
        claude_local = vault / ".claude"
        claude_local.mkdir()
        (claude_local / "settings.local.json").write_text("{}")
        obs_dir = vault / ".obsidian"
        obs_dir.mkdir()
        (obs_dir / "community-plugins.json").write_text("[]")

        result = _check_vault_files(str(vault))
        assert result["complete"] is True

    def test_missing_files(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _check_vault_files(str(vault))
        assert result["complete"] is False
        assert "CLAUDE.md" in result["details"]


class TestCheckSettingsJson:
    """Tests for _check_settings_json."""

    def test_valid_settings(self, tmp_path):
        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        settings = config_dir / "settings.json"
        settings.write_text(json.dumps({
            "mcpServers": {"claude-mem": {}},
            "hooks": {"SessionStart": [{"hooks": [{"command": "claude-mem"}]}]},
            "env": {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
        }))
        with patch("obsiforge.doctor.get_claude_config_dir", return_value=config_dir):
            result = _check_settings_json()
            assert result["valid"] is True

    def test_missing_settings(self, tmp_path):
        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        with patch("obsiforge.doctor.get_claude_config_dir", return_value=config_dir):
            result = _check_settings_json()
            assert result["valid"] is False
            assert "not found" in result["details"]