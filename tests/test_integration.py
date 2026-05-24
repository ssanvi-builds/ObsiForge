"""End-to-end integration test: simulate a fresh obsiforge init in an isolated tmpdir.

This test creates a fake home directory with a fake Claude config,
runs the vault setup and MCP config phases, and validates all generated files.

It does NOT require Obsidian, Node.js, or Claude Code to be installed —
it only tests the file-generation logic.
"""

from __future__ import annotations

import json

import pytest

from obsiforge.phases.mcp_config import (
    _write_mcp_json,
    _write_settings_local,
)
from obsiforge.phases.vault import (
    REQUIRED_PLUGINS,
    _create_directory_structure,
    _generate_claude_md,
    _generate_memory_md,
    _generate_user_preferences_md,
    _register_vault_in_obsidian,
    _write_appearance_json,
    _write_community_plugins,
    _write_mcp_connector_config,
    _write_rest_api_config,
)


@pytest.fixture
def fake_home(tmp_path):
    """Create a fake home directory with all required structure."""
    home = tmp_path / "fake_home"
    home.mkdir()

    # Create .claude config dir
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.json"
    settings.write_text(json.dumps({
        "mcpServers": {},
        "hooks": {},
        "env": {},
    }))

    return home


@pytest.fixture
def fake_vault(tmp_path):
    """Create a fake vault directory."""
    vault = tmp_path / "test-vault"
    vault.mkdir()
    return vault


class TestFullInitFlow:
    """Simulate the full obsiforge init flow in an isolated environment."""

    def test_vault_phase_creates_all_files(self, fake_vault):
        """Phase 2 should create all vault directories, configs, and templates."""
        vault_path = str(fake_vault)
        vault_name = "test-vault"

        # Run vault phase
        from obsiforge.phases.vault import run as vault_run
        result = vault_run(
            vault_name=vault_name,
            vault_path=vault_path,
            dry_run=False,
            skip_semantic=False,
            non_interactive=True,
        )

        # Validate result dict
        assert result["vault_name"] == vault_name
        assert result["vault_path"] == str(fake_vault)
        assert isinstance(result["rest_api_port"], int)
        assert isinstance(result["mcp_http_port"], int)
        assert isinstance(result["api_key"], str)
        assert len(result["api_key"]) == 64
        assert isinstance(result["bearer_token"], str)
        assert len(result["bearer_token"]) >= 44

        # Validate directory structure
        assert (fake_vault / "Claude").is_dir()
        assert (fake_vault / ".claude" / "skills" / "consolidate").is_dir()
        assert (fake_vault / ".claude" / "skills" / "dashboard").is_dir()
        assert (fake_vault / ".obsidian" / "plugins" / "mcp-tools-istefox").is_dir()
        assert (fake_vault / ".obsidian" / "plugins" / "obsidian-local-rest-api").is_dir()

        # Validate workspace.json exists
        workspace_json = fake_vault / ".obsidian" / "workspace.json"
        assert workspace_json.exists()
        workspace_data = json.loads(workspace_json.read_text())
        assert isinstance(workspace_data, dict)

        # Validate community-plugins.json
        plugins_file = fake_vault / ".obsidian" / "community-plugins.json"
        assert plugins_file.exists()
        plugins = json.loads(plugins_file.read_text())
        for p in REQUIRED_PLUGINS:
            assert p in plugins

        # Validate REST API config
        rest_config = (
            fake_vault / ".obsidian" / "plugins" / "obsidian-local-rest-api" / "data.json"
        )
        assert rest_config.exists()
        rest_data = json.loads(rest_config.read_text())
        assert "port" in rest_data
        assert "apiKey" in rest_data
        assert rest_data["enableSecureServer"] is True

        # Validate MCP Connector config
        mcp_config = (
            fake_vault / ".obsidian" / "plugins" / "mcp-tools-istefox" / "data.json"
        )
        assert mcp_config.exists()
        mcp_data = json.loads(mcp_config.read_text())
        assert "mcpTransport" in mcp_data
        assert "bearerToken" in mcp_data["mcpTransport"]
        assert "semanticSearch" in mcp_data

        # Validate CLAUDE.md
        claude_md = fake_vault / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert "Memory Architecture" in content
        assert "3-layer" in content
        # vault_name.title() transforms "test-vault" to "Test-Vault"
        assert vault_name.title() in content

        # Validate MEMORY.md
        memory_md = fake_vault / "Claude" / "MEMORY.md"
        assert memory_md.exists()
        assert "pointer" in memory_md.read_text().lower()

    def test_mcp_config_phase_creates_files(self, fake_vault, fake_home):
        """Phase 3 should create .mcp.json and settings.local.json."""
        vault_path = str(fake_vault)
        vault_name = "test-vault"
        mcp_port = 27201
        bearer_token = "test-bearer-token-1234567890abcdef"

        # Create .mcp.json (doesn't need get_claude_config_dir)
        _write_mcp_json(
            vault_path=vault_path,
            vault_name=vault_name,
            mcp_http_port=mcp_port,
            bearer_token=bearer_token,
            dry_run=False,
        )

        # Create settings.local.json
        _write_settings_local(
            vault_path=vault_path,
            vault_name=vault_name,
            dry_run=False,
        )

        # Validate .mcp.json
        mcp_json = fake_vault / ".mcp.json"
        assert mcp_json.exists()
        mcp_data = json.loads(mcp_json.read_text())
        assert "mcpServers" in mcp_data
        # Server name should be vault-specific
        expected_server = f"obsidian-mcp-tools-{vault_name}"
        assert expected_server in mcp_data["mcpServers"]
        obsidian_mcp = mcp_data["mcpServers"][expected_server]
        assert obsidian_mcp["type"] == "streamable-http"
        assert f":{mcp_port}/mcp" in obsidian_mcp["url"]
        assert obsidian_mcp["headers"]["Authorization"] == f"Bearer {bearer_token}"

        # Validate settings.local.json
        settings_local = fake_vault / ".claude" / "settings.local.json"
        assert settings_local.exists()
        local_data = json.loads(settings_local.read_text())
        assert "permissions" in local_data
        assert "allow" in local_data["permissions"]
        assert "enabledMcpjsonServers" in local_data
        # Server name should be vault-specific
        expected_server = f"obsidian-mcp-tools-{vault_name}"
        assert expected_server in local_data["enabledMcpjsonServers"]

    def test_dry_run_creates_no_files(self, tmp_path):
        """Dry-run mode should not create any files."""
        vault = tmp_path / "dry-vault"
        vault.mkdir()

        from obsiforge.phases.vault import run as vault_run
        result = vault_run(
            vault_name="dry-vault",
            vault_path=str(vault),
            dry_run=True,
            skip_semantic=False,
            non_interactive=True,
        )

        # Vault phase returns config even in dry-run
        assert "rest_api_port" in result

        # But no files should be written
        assert not (vault / "CLAUDE.md").exists()
        assert not (vault / ".obsidian" / "community-plugins.json").exists()
        assert not (vault / "Claude" / "MEMORY.md").exists()

    def test_idempotent_vault_setup(self, fake_vault):
        """Running vault phase twice should not corrupt existing files."""
        vault_path = str(fake_vault)
        vault_name = "test-vault"

        from obsiforge.phases.vault import run as vault_run

        # First run
        result1 = vault_run(
            vault_name=vault_name,
            vault_path=vault_path,
            dry_run=False,
            skip_semantic=False,
            non_interactive=True,
        )

        # Second run
        result2 = vault_run(
            vault_name=vault_name,
            vault_path=vault_path,
            dry_run=False,
            skip_semantic=False,
            non_interactive=True,
        )

        # Both should succeed
        assert result1["vault_path"] == result2["vault_path"]

        # community-plugins.json should not have duplicates
        plugins_file = fake_vault / ".obsidian" / "community-plugins.json"
        plugins = json.loads(plugins_file.read_text())
        assert len(plugins) == len(set(plugins))  # No duplicates

        # CLAUDE.md should still contain memory section
        content = (fake_vault / "CLAUDE.md").read_text()
        assert "Memory Architecture" in content


class TestVaultFileDetails:
    """Test individual vault file generation in detail."""

    def test_community_plugins_json_format(self, fake_vault):
        """community-plugins.json should be valid JSON with required plugins."""
        # Ensure .obsidian directory exists
        (fake_vault / ".obsidian").mkdir(parents=True, exist_ok=True)
        _write_community_plugins(fake_vault, dry_run=False)
        data = json.loads((fake_vault / ".obsidian" / "community-plugins.json").read_text())
        assert isinstance(data, list)
        assert "mcp-tools-istefox" in data
        assert "obsidian-local-rest-api" in data

    def test_rest_api_config_values(self, fake_vault):
        """REST API config should have port and API key."""
        _write_rest_api_config(fake_vault, 27124, "test-api-key-1234", dry_run=False)
        rest_api_data = (
            fake_vault / ".obsidian" / "plugins"
            / "obsidian-local-rest-api" / "data.json"
        )
        data = json.loads(rest_api_data.read_text())
        assert data["port"] == 27124
        assert data["apiKey"] == "test-api-key-1234"
        assert data["enableSecureServer"] is True

    def test_mcp_connector_config_structure(self, fake_vault):
        """MCP Connector config should have bearer token and semantic search."""
        _write_mcp_connector_config(fake_vault, "test-token-12345678", dry_run=False)
        data = json.loads(
            (fake_vault / ".obsidian" / "plugins" / "mcp-tools-istefox" / "data.json").read_text()
        )
        assert data["mcpTransport"]["bearerToken"] == "test-token-12345678"
        assert data["semanticSearch"]["provider"] == "native"

    def test_claude_md_content(self, fake_vault):
        """CLAUDE.md should contain vault name and memory architecture."""
        _generate_claude_md("my-project", fake_vault, dry_run=False)
        content = (fake_vault / "CLAUDE.md").read_text()
        assert "My-Project" in content
        assert "3-layer" in content
        assert "search_vault_smart" in content

    def test_memory_md_pointer(self, fake_vault):
        """MEMORY.md should be a pointer file referencing user-preferences."""
        # Ensure Claude directory exists
        (fake_vault / "Claude").mkdir(parents=True, exist_ok=True)
        _generate_memory_md(fake_vault, dry_run=False)
        content = (fake_vault / "Claude" / "MEMORY.md").read_text()
        assert "pointer" in content.lower()
        assert "get_vault_file" in content
        assert "user-preferences" in content
        assert "/dashboard" in content

    def test_directory_structure(self, fake_vault):
        """All required directories should be created."""
        dirs = _create_directory_structure(fake_vault)
        dir_names = [d.name for d in dirs]
        assert "Claude" in dir_names
        assert "consolidate" in dir_names
        assert "dashboard" in dir_names
        assert "mcp-tools-istefox" in dir_names
        assert "obsidian-local-rest-api" in dir_names

    def test_user_preferences_md_content(self, fake_vault):
        """user-preferences.md should have placeholders and auto-detected OS."""
        (fake_vault / "Claude").mkdir(parents=True, exist_ok=True)
        _generate_user_preferences_md(fake_vault, dry_run=False, non_interactive=True)
        prefs_file = fake_vault / "Claude" / "user-preferences.md"
        assert prefs_file.exists()
        content = prefs_file.read_text()
        assert "User Preferences" in content
        assert "Communication" in content
        assert "Development" in content
        # OS should be auto-detected (not a placeholder)
        import platform
        expected_os = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(
            platform.system(), platform.system()
        )
        assert expected_os in content

    def test_appearance_json_dark_theme(self, fake_vault):
        """appearance.json should set dark theme."""
        (fake_vault / ".obsidian").mkdir(parents=True, exist_ok=True)
        _write_appearance_json(fake_vault, dry_run=False)
        appearance = fake_vault / ".obsidian" / "appearance.json"
        assert appearance.exists()
        data = json.loads(appearance.read_text())
        assert data["cssTheme"] == "obsidian"

    def test_dashboard_skill_content(self, fake_vault):
        """Dashboard skill should reference user-preferences.md and /consolidate."""
        from obsiforge.phases.vault import _write_skills
        _write_skills("test-vault", fake_vault, dry_run=False)
        dashboard = fake_vault / ".claude" / "skills" / "dashboard" / "SKILL.md"
        assert dashboard.exists()
        content = dashboard.read_text()
        assert "user-preferences.md" in content
        assert "/consolidate" in content

    def test_consolidate_skill_content(self, fake_vault):
        """Consolidate skill should reference filesystem paths and Vault Conventions."""
        from obsiforge.phases.vault import _write_skills
        _write_skills("test-vault", fake_vault, dry_run=False)
        consolidate = fake_vault / ".claude" / "skills" / "consolidate" / "SKILL.md"
        assert consolidate.exists()
        content = consolidate.read_text()
        assert "absolute paths" in content
        assert "Vault Conventions" in content
        assert "frontmatter" in content


class TestVaultRegistration:
    """Test _register_vault_in_obsidian function."""

    def test_register_creates_obsidian_json(self, tmp_path):
        """Should create obsidian.json with the vault registered and open=true."""
        vault_dir = tmp_path / "my-vault"
        vault_dir.mkdir()

        config_dir = tmp_path / "obsidian_config"
        config_dir.mkdir()

        import obsiforge.utils.platform as platform
        original_fn = platform.get_obsidian_config_dir

        platform.get_obsidian_config_dir = lambda: config_dir
        try:
            result = _register_vault_in_obsidian(vault_dir, dry_run=False)
            assert result is True

            config_file = config_dir / "obsidian.json"
            assert config_file.exists()

            data = json.loads(config_file.read_text())
            assert "vaults" in data
            vaults = data["vaults"]
            assert len(vaults) == 1

            vault_info = next(iter(vaults.values()))
            assert vault_info["path"] == str(vault_dir.resolve())
            assert "ts" in vault_info
            assert vault_info["open"] is True
            assert data["cli"] is True
        finally:
            platform.get_obsidian_config_dir = original_fn

    def test_register_idempotent(self, tmp_path):
        """Should not duplicate entries if vault is already registered."""
        vault_dir = tmp_path / "my-vault"
        vault_dir.mkdir()

        config_dir = tmp_path / "obsidian_config"
        config_dir.mkdir()

        import obsiforge.utils.platform as platform
        original_fn = platform.get_obsidian_config_dir

        platform.get_obsidian_config_dir = lambda: config_dir
        try:
            _register_vault_in_obsidian(vault_dir, dry_run=False)
            _register_vault_in_obsidian(vault_dir, dry_run=False)

            config_file = config_dir / "obsidian.json"
            data = json.loads(config_file.read_text())
            vaults = data["vaults"]
            # Should have exactly 1 entry, not 2
            assert len(vaults) == 1
        finally:
            platform.get_obsidian_config_dir = original_fn

    def test_register_preserves_existing_vaults(self, tmp_path):
        """Should preserve other vaults and remove open=true from them."""
        vault_dir = tmp_path / "new-vault"
        vault_dir.mkdir()

        config_dir = tmp_path / "obsidian_config"
        config_dir.mkdir()
        config_file = config_dir / "obsidian.json"
        existing_data = {
            "vaults": {
                "abc123def45678": {
                    "path": "/Users/test/existing-vault",
                    "ts": 1700000000000,
                    "open": True,
                }
            }
        }
        config_file.write_text(json.dumps(existing_data))

        import obsiforge.utils.platform as platform
        original_fn = platform.get_obsidian_config_dir

        platform.get_obsidian_config_dir = lambda: config_dir
        try:
            _register_vault_in_obsidian(vault_dir, dry_run=False)

            data = json.loads(config_file.read_text())
            vaults = data["vaults"]
            assert len(vaults) == 2
            assert "abc123def45678" in vaults
            assert vaults["abc123def45678"]["path"] == "/Users/test/existing-vault"
            # Other vault should NOT have open=true anymore
            assert "open" not in vaults["abc123def45678"]
            # Our vault should have open=true
            our_vault = next(
                v for v in vaults.values()
                if v["path"] == str(vault_dir.resolve())
            )
            assert our_vault["open"] is True
        finally:
            platform.get_obsidian_config_dir = original_fn

    def test_register_creates_backup(self, tmp_path):
        """Should create a .bak file before modifying obsidian.json."""
        vault_dir = tmp_path / "my-vault"
        vault_dir.mkdir()

        config_dir = tmp_path / "obsidian_config"
        config_dir.mkdir()
        config_file = config_dir / "obsidian.json"
        config_file.write_text('{"vaults": {}}')

        import obsiforge.utils.platform as platform
        original_fn = platform.get_obsidian_config_dir

        platform.get_obsidian_config_dir = lambda: config_dir
        try:
            _register_vault_in_obsidian(vault_dir, dry_run=False)

            backup = config_dir / "obsidian.json.bak"
            assert backup.exists()
        finally:
            platform.get_obsidian_config_dir = original_fn


class TestMcpConfigDetails:
    """Test MCP config file generation in detail."""

    def test_mcp_json_streamable_http_format(self, fake_vault):
        """.mcp.json should use streamable-http format with vault-specific name."""
        _write_mcp_json(
            vault_path=str(fake_vault),
            vault_name="test",
            mcp_http_port=27201,
            bearer_token="token-abc123",
            dry_run=False,
        )
        data = json.loads((fake_vault / ".mcp.json").read_text())
        mcp = data["mcpServers"]["obsidian-mcp-tools-test"]
        assert mcp["type"] == "streamable-http"
        assert "http://127.0.0.1:27201/mcp" in mcp["url"]
        assert mcp["headers"]["Authorization"] == "Bearer token-abc123"

    def test_settings_local_permissions(self, fake_vault):
        """settings.local.json should include expanded MCP tool permissions."""
        _write_settings_local(
            vault_path=str(fake_vault),
            vault_name="test",
            dry_run=False,
        )
        data = json.loads((fake_vault / ".claude" / "settings.local.json").read_text())
        allow = data["permissions"]["allow"]
        # Server name should be vault-specific in tool permissions
        assert "mcp__obsidian-mcp-tools-test__get_vault_file" in allow
        assert "mcp__obsidian-mcp-tools-test__get_server_info" in allow
        assert "mcp__obsidian-mcp-tools-test__list_vault_files" in allow
        assert "mcp__obsidian-mcp-tools-test__create_vault_file" in allow
        assert "mcp__obsidian-mcp-tools-test__patch_vault_file" in allow
        assert "mcp__obsidian-mcp-tools-test__append_to_vault_file" in allow
        assert "mcp__obsidian-mcp-tools-test__update_active_file" in allow
        assert "mcp__obsidian-mcp-tools-test__search_vault_smart" in allow
        assert "mcp__obsidian-mcp-tools-test__search_vault_simple" in allow
        assert "mcp__obsidian-mcp-tools-test__get_backlinks" in allow
        assert "mcp__obsidian-mcp-tools-test__get_outgoing_links" in allow
        assert "mcp__obsidian-mcp-tools-test__get_files_by_tag" in allow
        assert "mcp__obsidian-mcp-tools-test__list_tags" in allow
        # claude-mem
        assert "mcp__plugin_claude-mem_mcp-search__search" in allow
        assert "mcp__plugin_claude-mem_mcp-search__timeline" in allow
        assert "mcp__plugin_claude-mem_mcp-search__get_observations" in allow
        assert len(allow) >= 15


class TestDoctorIntegration:
    """Test doctor checks against a fully configured vault."""

    def test_doctor_detects_missing_plugins(self, fake_vault):
        """Doctor should detect missing community plugins."""
        from obsiforge.doctor import _check_plugins_enabled

        result = _check_plugins_enabled(str(fake_vault))
        assert result["missing"] == {"mcp-tools-istefox", "obsidian-local-rest-api"}

    def test_doctor_detects_enabled_plugins(self, fake_vault):
        """Doctor should detect all enabled plugins."""
        from obsiforge.doctor import _check_plugins_enabled

        plugins_file = fake_vault / ".obsidian" / "community-plugins.json"
        plugins_file.parent.mkdir(parents=True, exist_ok=True)
        plugins_file.write_text(json.dumps(REQUIRED_PLUGINS))

        result = _check_plugins_enabled(str(fake_vault))
        assert result["missing"] == set()

    def test_doctor_detects_vault_files(self, fake_vault):
        """Doctor should detect missing vault files."""
        from obsiforge.doctor import _check_vault_files

        # Empty vault should report missing files
        result = _check_vault_files(str(fake_vault))
        assert result["complete"] is False
        assert "CLAUDE.md" in result["details"]

    def test_doctor_confirms_complete_vault(self, fake_vault):
        """Doctor should confirm all files present in a configured vault."""
        from obsiforge.doctor import _check_vault_files
        from obsiforge.phases.vault import run as vault_run

        # Set up vault properly
        vault_run(
            vault_name="test",
            vault_path=str(fake_vault),
            dry_run=False,
            skip_semantic=False,
            non_interactive=True,
        )

        # Also create files from Phase 3 that _check_vault_files expects
        (fake_vault / ".mcp.json").write_text('{}')
        settings_dir = fake_vault / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.local.json").write_text('{}')

        result = _check_vault_files(str(fake_vault))
        assert result["complete"] is True