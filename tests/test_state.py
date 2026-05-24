"""Tests for obsiforge.utils.state module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from obsiforge.utils.state import (
    PHASES,
    is_phase_complete,
    load_state,
    mark_phase_complete,
    reset_state,
    save_state,
)


@pytest.fixture
def state_dir(tmp_path):
    """Use a temporary directory for state files."""
    state_file = tmp_path / "obsiforge-state.json"
    with patch("obsiforge.utils.state.STATE_FILE", state_file), \
         patch("obsiforge.utils.state.STATE_DIR", tmp_path):
        yield state_file


class TestLoadState:
    """Tests for load_state function."""

    def test_load_missing_file(self, state_dir):
        state = load_state()
        assert state["completed_phases"] == []
        assert state["vaults"] == {}
        assert state["version"] == "0.1.0"

    def test_load_existing_file(self, state_dir):
        data = {"completed_phases": ["prerequisites"], "vaults": {}, "version": "0.1.0"}
        state_dir.write_text(json.dumps(data))
        state = load_state()
        assert "prerequisites" in state["completed_phases"]

    def test_load_corrupted_file(self, state_dir):
        state_dir.write_text("not json{{{")
        state = load_state()
        assert state["completed_phases"] == []


class TestSaveState:
    """Tests for save_state function."""

    def test_save_creates_file(self, state_dir):
        state = {"completed_phases": [], "vaults": {}, "version": "0.1.0"}
        save_state(state)
        assert state_dir.exists()
        saved = json.loads(state_dir.read_text())
        assert saved == state


class TestMarkPhaseComplete:
    """Tests for mark_phase_complete function."""

    def test_mark_global_phase(self, state_dir):
        mark_phase_complete("prerequisites")
        state = load_state()
        assert "prerequisites" in state["completed_phases"]

    def test_mark_vault_phase(self, state_dir):
        mark_phase_complete("vault", "my-vault")
        state = load_state()
        assert "vault:my-vault" in state["completed_phases"]

    def test_mark_duplicate_phase(self, state_dir):
        mark_phase_complete("prerequisites")
        mark_phase_complete("prerequisites")
        state = load_state()
        assert state["completed_phases"].count("prerequisites") == 1

    def test_invalid_phase_raises(self, state_dir):
        with pytest.raises(ValueError, match="Unknown phase"):
            mark_phase_complete("nonexistent_phase")


class TestIsPhaseComplete:
    """Tests for is_phase_complete function."""

    def test_phase_not_complete(self, state_dir):
        assert not is_phase_complete("prerequisites")

    def test_phase_is_complete(self, state_dir):
        mark_phase_complete("prerequisites")
        assert is_phase_complete("prerequisites")

    def test_vault_phase_complete(self, state_dir):
        mark_phase_complete("vault", "work")
        assert is_phase_complete("vault", "work")
        assert not is_phase_complete("vault", "personal")


class TestResetState:
    """Tests for reset_state function."""

    def test_reset_removes_file(self, state_dir):
        mark_phase_complete("prerequisites")
        assert state_dir.exists()
        reset_state()
        assert not state_dir.exists()

    def test_reset_missing_file_ok(self, state_dir):
        reset_state()  # Should not raise


class TestPhases:
    """Tests for phase constants."""

    def test_phases_are_defined(self):
        assert "prerequisites" in PHASES
        assert "claude_mem" in PHASES
        assert "vault" in PHASES
        assert "mcp_config" in PHASES
        assert "verify" in PHASES