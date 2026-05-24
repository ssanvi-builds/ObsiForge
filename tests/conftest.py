"""Shared test fixtures for ObsiForge tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_state_file(monkeypatch, tmp_path):
    """Redirect state file writes to a temp directory so tests never touch ~/.claude.

    Patches the module-level STATE_DIR and STATE_FILE constants and sets the
    OBSIFORGE_STATE_DIR environment variable so that both in-process calls and
    subprocess invocations (test_smoke.py run_cli) use tmp_path.
    """
    from obsiforge.utils import state as state_mod

    state_dir = tmp_path / "state_home"
    state_dir.mkdir()
    state_file = state_dir / "obsiforge-state.json"

    monkeypatch.setattr(state_mod, "STATE_DIR", state_dir)
    monkeypatch.setattr(state_mod, "STATE_FILE", state_file)
    monkeypatch.setenv("OBSIFORGE_STATE_DIR", str(state_dir))

    yield state_file

    monkeypatch.delenv("OBSIFORGE_STATE_DIR", raising=False)


@pytest.fixture(autouse=True)
def _mock_open_obsidian(monkeypatch):
    """Prevent tests from opening Obsidian or writing to the real obsidian.json.

    _open_obsidian calls _register_vault_in_obsidian which writes to the real
    obsidian.json config file. This fixture prevents that by mocking the function.
    Tests that specifically test _register_vault_in_obsidian (like TestVaultRegistration)
    call it directly and provide their own mocks for get_obsidian_config_dir.
    """
    from obsiforge.phases import vault

    monkeypatch.setattr(vault, "_open_obsidian", lambda *a, **kw: True)
    monkeypatch.setattr(vault, "_is_obsidian_running", lambda: False)
    monkeypatch.setattr(vault, "_quit_obsidian", lambda: True)
    monkeypatch.setattr(vault, "_launch_obsidian", lambda: None)
    monkeypatch.setattr(vault, "_wait_for_obsidian_ready", lambda *a, **kw: True)
    monkeypatch.setattr(vault, "_discover_actual_mcp_port", lambda port, **kw: port)