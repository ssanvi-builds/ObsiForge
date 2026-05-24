"""Tests for obsiforge.doctor module."""

import json
from unittest.mock import MagicMock, patch

from obsiforge.doctor import (
    _check_plugins_enabled,
    _check_settings_json,
    _check_vault_files,
    _check_workspace_json,
)
from obsiforge.utils.obsidian import (
    check_port_in_use,
    is_obsidian_running,
)


class TestIsObsidianRunning:
    """Tests for is_obsidian_running."""

    def test_obsidian_running(self):
        with patch("obsiforge.utils.obsidian.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")
            result = is_obsidian_running()
            assert result["running"] is True
            assert "12345" in result["pids"]

    def test_obsidian_not_running(self):
        with patch("obsiforge.utils.obsidian.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = is_obsidian_running()
            assert result["running"] is False


class TestCheckPortInUse:
    """Tests for check_port_in_use."""

    def test_port_available(self):
        with patch("obsiforge.utils.obsidian.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1  # Connection refused
            mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
            assert check_port_in_use(9999) is False


class TestCheckPluginsEnabled:
    """Tests for _check_plugins_enabled."""

    def test_all_plugins_enabled(self, tmp_path):
        vault = tmp_path / "vault"
        obs_dir = vault / ".obsidian"
        obs_dir.mkdir(parents=True)
        plugins_file = obs_dir / "community-plugins.json"
        plugins_file.write_text(json.dumps([
            "mcp-tools-istefox",
            "obsidian-local-rest-api",
        ]))
        result = _check_plugins_enabled(str(vault))
        assert result["missing"] == set()
        assert "2/2" in result["details"]

    def test_missing_plugins(self, tmp_path):
        vault = tmp_path / "vault"
        obs_dir = vault / ".obsidian"
        obs_dir.mkdir(parents=True)
        plugins_file = obs_dir / "community-plugins.json"
        plugins_file.write_text(json.dumps(["mcp-tools-istefox"]))
        result = _check_plugins_enabled(str(vault))
        assert "obsidian-local-rest-api" in result["missing"]

    def test_no_plugins_file(self, tmp_path):
        vault = tmp_path / "vault"
        result = _check_plugins_enabled(str(vault))
        assert result["missing"] == {"mcp-tools-istefox", "obsidian-local-rest-api"}


class TestCheckWorkspaceJson:
    """Tests for _check_workspace_json."""

    def test_workspace_json_exists(self, tmp_path):
        vault = tmp_path / "vault"
        obs_dir = vault / ".obsidian"
        obs_dir.mkdir(parents=True)
        (obs_dir / "workspace.json").write_text("{}")
        result = _check_workspace_json(str(vault))
        assert result["valid"] is True

    def test_workspace_json_missing(self, tmp_path):
        vault = tmp_path / "vault"
        result = _check_workspace_json(str(vault))
        assert result["valid"] is False
        assert "not found" in result["details"]

    def test_workspace_json_invalid(self, tmp_path):
        vault = tmp_path / "vault"
        obs_dir = vault / ".obsidian"
        obs_dir.mkdir(parents=True)
        (obs_dir / "workspace.json").write_text("not json")
        result = _check_workspace_json(str(vault))
        assert result["valid"] is False


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
        (obs_dir / "workspace.json").write_text("{}")

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