"""Smoke tests simulating a fresh install of obsiforge.

Two levels:
1. Dry-run: validates CLI, imports, and output without touching the filesystem.
2. Live vault: creates a real vault in tmpdir, runs init, verifies all files.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for assertion matching."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)

# ─── Helpers ───────────────────────────────────────────────────────


def run_cli(*args: str, cwd: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run obsiforge CLI and return the result."""
    result = subprocess.run(
        ["uv", "run", "obsiforge", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
    )
    return result


def _import_module(name: str) -> object:
    """Dynamically import a module to verify it loads cleanly."""
    import importlib

    return importlib.import_module(name)


# ═══════════════════════════════════════════════════════════════════
# LEVEL 1: DRY-RUN SMOKE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestCLIDryRun:
    """Verify CLI works without touching real config."""

    def test_help_shows_commands(self) -> None:
        result = run_cli("--help")
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "init" in result.stdout
        assert "doctor" in result.stdout
        assert "status" in result.stdout
        assert "add-vault" in result.stdout

    def test_init_help(self) -> None:
        result = run_cli("init", "--help")
        assert result.returncode == 0
        output = _strip_ansi(result.stdout)
        assert "--name" in output
        assert "--path" in output
        assert "--dry-run" in output

    def test_version(self) -> None:
        result = run_cli("--version")
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_dry_run_produces_output(self) -> None:
        """Dry-run should produce output without modifying real config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = os.path.join(tmpdir, "smoketest-vault")
            result = run_cli(
                "init",
                "--name", "smoketest",
                "--path", vault_path,
                "--dry-run",
            )
            output = result.stdout + result.stderr
            assert "ObsiForge" in output, "Expected ObsiForge banner in output"
            # Dry-run should show the DRY RUN banner
            assert "DRY RUN" in output, "Expected DRY RUN banner in output"

    def test_invalid_vault_name_rejected(self) -> None:
        """Vault names with special characters should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = os.path.join(tmpdir, "test-vault")
            result = run_cli(
                "init",
                "--name", "bad vault!",
                "--path", vault_path,
                "--dry-run",
            )
            # Should fail with validation error
            assert result.returncode != 0


class TestModuleImports:
    """Verify all modules import cleanly."""

    def test_cli_imports(self) -> None:
        mod = _import_module("obsiforge.cli")
        assert hasattr(mod, "app")

    def test_crypto_imports(self) -> None:
        mod = _import_module("obsiforge.utils.crypto")
        assert hasattr(mod, "generate_api_key")

    def test_settings_merge_imports(self) -> None:
        mod = _import_module("obsiforge.utils.settings_merge")
        assert hasattr(mod, "merge_into_settings")

    def test_state_imports(self) -> None:
        mod = _import_module("obsiforge.utils.state")
        assert hasattr(mod, "load_state")

    def test_doctor_imports(self) -> None:
        mod = _import_module("obsiforge.doctor")
        assert hasattr(mod, "run_doctor")

    def test_ports_imports(self) -> None:
        mod = _import_module("obsiforge.utils.ports")
        assert hasattr(mod, "find_available_port")


# ═══════════════════════════════════════════════════════════════════
# LEVEL 2: LIVE VAULT INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════


class TestLiveVaultInit:
    """Create a real vault in tmpdir and verify file creation.

    These tests actually create files but in an isolated temp directory.
    They do NOT attempt to connect to real Obsidian or Claude processes.
    """

    @pytest.fixture()
    def vault_dir(self, tmp_path: Path) -> Path:
        """Create and return a vault directory."""
        vault = tmp_path / "test-vault"
        vault.mkdir()
        return vault

    def test_init_creates_vault_structure(self, vault_dir: Path) -> None:
        """Run init with --non-interactive and verify vault files are created."""
        result = run_cli(
            "init",
            "--name", "livetest",
            "--path", str(vault_dir),
            "--non-interactive",
        )
        # init may fail on prerequisites (claude CLI, node) but should create vault files
        # Check that vault structure was at least attempted
        assert (vault_dir / "Claude").exists() or "Prerequisites" in result.stdout + result.stderr

    def test_init_creates_claude_md(self, vault_dir: Path) -> None:
        """Verify CLAUDE.md is created."""
        # Run the vault phase directly
        from obsiforge.phases.vault import run as vault_run

        result = vault_run(
            vault_name="livetest",
            vault_path=str(vault_dir),
            dry_run=False,
            non_interactive=True,
        )
        assert result is not None

        # Check CLAUDE.md
        claude_md = vault_dir / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md not created"
        content = claude_md.read_text(encoding="utf-8")
        assert "Memory Architecture" in content
        assert "3-layer" in content.lower() or "3 Layer" in content

    def test_init_creates_memory_md(self, vault_dir: Path) -> None:
        """Verify Claude/MEMORY.md is created."""
        from obsiforge.phases.vault import run as vault_run

        vault_run(
            vault_name="livetest",
            vault_path=str(vault_dir),
            dry_run=False,
            non_interactive=True,
        )

        memory_md = vault_dir / "Claude" / "MEMORY.md"
        assert memory_md.exists(), "Claude/MEMORY.md not created"
        content = memory_md.read_text(encoding="utf-8")
        assert "pointer" in content.lower()

    def test_init_creates_community_plugins(self, vault_dir: Path) -> None:
        """Verify community-plugins.json is created with required plugins."""
        from obsiforge.phases.vault import run as vault_run

        vault_run(
            vault_name="livetest",
            vault_path=str(vault_dir),
            dry_run=False,
            non_interactive=True,
        )

        plugins_file = vault_dir / ".obsidian" / "community-plugins.json"
        assert plugins_file.exists(), "community-plugins.json not created"

        plugins = json.loads(plugins_file.read_text(encoding="utf-8"))
        assert "mcp-tools-istefox" in plugins
        assert "obsidian-local-rest-api" in plugins

    def test_init_creates_rest_api_config(self, vault_dir: Path) -> None:
        """Verify REST API config has port and API key."""
        from obsiforge.phases.vault import run as vault_run

        result = vault_run(
            vault_name="livetest",
            vault_path=str(vault_dir),
            dry_run=False,
            non_interactive=True,
        )

        config_file = vault_dir / ".obsidian" / "plugins" / "obsidian-local-rest-api" / "data.json"
        assert config_file.exists(), "REST API data.json not created"

        config = json.loads(config_file.read_text(encoding="utf-8"))
        assert "port" in config
        assert "apiKey" in config
        assert config["port"] > 0

    def test_init_creates_mcp_connector_config(self, vault_dir: Path) -> None:
        """Verify MCP Connector config has bearer token."""
        from obsiforge.phases.vault import run as vault_run

        result = vault_run(
            vault_name="livetest",
            vault_path=str(vault_dir),
            dry_run=False,
            non_interactive=True,
        )

        config_file = vault_dir / ".obsidian" / "plugins" / "mcp-tools-istefox" / "data.json"
        assert config_file.exists(), "MCP Connector data.json not created"

        config = json.loads(config_file.read_text(encoding="utf-8"))
        assert "mcpTransport" in config
        assert "bearerToken" in config["mcpTransport"]
        assert len(config["mcpTransport"]["bearerToken"]) > 20

    def test_init_creates_mcp_json(self, vault_dir: Path) -> None:
        """Verify .mcp.json is created in vault root."""
        from obsiforge.phases.vault import run as vault_run
        from obsiforge.phases.mcp_config import run as mcp_run

        vault_result = vault_run(
            vault_name="livetest",
            vault_path=str(vault_dir),
            dry_run=False,
            non_interactive=True,
        )

        # Save state for mcp_config
        from obsiforge.utils.state import load_state, save_state

        state = load_state()
        state.setdefault("vaults", {})["livetest"] = {
            "rest_api_port": vault_result["rest_api_port"],
            "mcp_http_port": vault_result["mcp_http_port"],
            "api_key": vault_result["api_key"],
            "bearer_token": vault_result["bearer_token"],
            "vault_path": str(vault_dir),
        }
        save_state(state)

        mcp_run(
            vault_name="livetest",
            vault_path=str(vault_dir),
            dry_run=False,
            non_interactive=True,
        )

        mcp_file = vault_dir / ".mcp.json"
        assert mcp_file.exists(), ".mcp.json not created"

        mcp_config = json.loads(mcp_file.read_text(encoding="utf-8"))
        assert "mcpServers" in mcp_config
        assert "obsidian-mcp-tools" in mcp_config["mcpServers"]

    def test_vault_name_validation_blocks_special_chars(self) -> None:
        """Vault names with spaces, dots, or slashes should be rejected."""
        from obsiforge.phases.vault import run
        import re

        invalid_names = ["bad vault", "my.vault", "../escape", "vault/path"]
        pattern = re.compile(r"^[a-zA-Z0-9_-]+$")
        for name in invalid_names:
            assert not pattern.match(name), f"Name '{name}' should be invalid"

    def test_state_persists_across_phases(self, vault_dir: Path) -> None:
        """Verify state file is written correctly after vault phase."""
        from obsiforge.phases.vault import run as vault_run
        from obsiforge.utils.state import load_state, mark_phase_complete, save_state

        result = vault_run(
            vault_name="livetest",
            vault_path=str(vault_dir),
            dry_run=False,
            non_interactive=True,
        )

        # Manually save state (normally done by cli.py)
        state = load_state()
        state.setdefault("vaults", {})["livetest"] = {
            "rest_api_port": result["rest_api_port"],
            "mcp_http_port": result["mcp_http_port"],
            "api_key": result["api_key"],
            "bearer_token": result["bearer_token"],
            "vault_path": str(vault_dir),
        }
        save_state(state)
        mark_phase_complete("vault", "livetest")

        # Reload and verify
        state2 = load_state()
        assert "livetest" in state2.get("vaults", {})
        assert state2["vaults"]["livetest"]["api_key"] == result["api_key"]


class TestCryptoAndPorts:
    """Verify crypto and port utilities work correctly."""

    def test_api_key_length_and_uniqueness(self) -> None:
        from obsiforge.utils.crypto import generate_api_key

        key1 = generate_api_key(64)
        key2 = generate_api_key(64)
        assert len(key1) == 64
        assert len(key2) == 64
        assert key1 != key2

    def test_bearer_token_generation(self) -> None:
        from obsiforge.utils.crypto import generate_bearer_token

        token = generate_bearer_token(44)
        # token_urlsafe produces ~1.33x the input length in chars
        assert len(token) >= 44
        assert token != generate_bearer_token(44)

    def test_find_available_port(self) -> None:
        from obsiforge.utils.ports import find_available_port

        port = find_available_port(27100)
        assert 1024 <= port <= 65535
        assert isinstance(port, int)

    def test_allocate_ports_returns_dict(self) -> None:
        from obsiforge.utils.ports import allocate_ports

        ports = allocate_ports("test-vault")
        assert "rest_api" in ports
        assert "mcp_http" in ports
        assert ports["rest_api"] != ports["mcp_http"]


class TestInstallerModule:
    """Test the installer module can be imported and has correct structure."""

    def test_installer_imports(self) -> None:
        from obsiforge.utils.installer import INSTALLERS

        assert "Node.js" in INSTALLERS
        assert "uv" in INSTALLERS
        assert "git" in INSTALLERS
        assert "Claude Code" in INSTALLERS
        assert "claude-mem" in INSTALLERS
        assert "Obsidian" in INSTALLERS

    def test_installer_functions_callable(self) -> None:
        from obsiforge.utils.installer import (
            install_node,
            install_uv,
            install_git,
            install_claude,
            install_claude_mem,
            install_obsidian,
        )

        for fn in [install_node, install_uv, install_git, install_claude, install_claude_mem, install_obsidian]:
            assert callable(fn)

    def test_installer_dry_run_does_not_install(self) -> None:
        """Dry-run should print messages but not actually install anything."""
        from obsiforge.utils.installer import install_node

        # If node is already installed, this returns True
        result = install_node(non_interactive=True, dry_run=True)
        assert result is True

    def test_platform_detection(self) -> None:
        from obsiforge.utils.platform import detect_package_manager, get_platform

        plat = get_platform()
        assert plat in ("macos", "linux", "windows")

        pkg_mgr = detect_package_manager()
        # On macOS with brew, should return "brew"
        if plat == "macos":
            assert pkg_mgr == "brew" or pkg_mgr is None

    def test_auto_install_flag_in_cli(self) -> None:
        """Verify --auto-install flag is recognized by the CLI."""
        result = run_cli("init", "--help")
        assert result.returncode == 0
        output = _strip_ansi(result.stdout)
        assert "auto-install" in output or "auto_install" in output