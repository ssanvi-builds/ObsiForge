"""Tests for obsiforge.utils.state module."""

import json

import pytest

from obsiforge.utils.state import (
    PHASES,
    is_phase_complete,
    load_state,
    mark_phase_complete,
    reset_state,
    save_state,
)


class TestLoadState:
    """Tests for load_state function."""

    def test_load_missing_file(self, _isolate_state_file):
        state = load_state()
        assert state["completed_phases"] == []
        assert state["vaults"] == {}
        assert state["version"] == "0.1.0"

    def test_load_existing_file(self, _isolate_state_file):
        data = {"completed_phases": ["prerequisites"], "vaults": {}, "version": "0.1.0"}
        _isolate_state_file.write_text(json.dumps(data))
        state = load_state()
        assert "prerequisites" in state["completed_phases"]

    def test_load_corrupted_file(self, _isolate_state_file):
        _isolate_state_file.write_text("not json{{{")
        state = load_state()
        assert state["completed_phases"] == []


class TestSaveState:
    """Tests for save_state function."""

    def test_save_creates_file(self, _isolate_state_file):
        state = {"completed_phases": [], "vaults": {}, "version": "0.1.0"}
        save_state(state)
        assert _isolate_state_file.exists()
        saved = json.loads(_isolate_state_file.read_text())
        assert saved == state


class TestMarkPhaseComplete:
    """Tests for mark_phase_complete function."""

    def test_mark_global_phase(self, _isolate_state_file):
        mark_phase_complete("prerequisites")
        state = load_state()
        assert "prerequisites" in state["completed_phases"]

    def test_mark_vault_phase(self, _isolate_state_file):
        mark_phase_complete("vault", "my-vault")
        state = load_state()
        assert "vault:my-vault" in state["completed_phases"]

    def test_mark_duplicate_phase(self, _isolate_state_file):
        mark_phase_complete("prerequisites")
        mark_phase_complete("prerequisites")
        state = load_state()
        assert state["completed_phases"].count("prerequisites") == 1

    def test_invalid_phase_raises(self, _isolate_state_file):
        with pytest.raises(ValueError, match="Unknown phase"):
            mark_phase_complete("nonexistent_phase")


class TestIsPhaseComplete:
    """Tests for is_phase_complete function."""

    def test_phase_not_complete(self, _isolate_state_file):
        assert not is_phase_complete("prerequisites")

    def test_phase_is_complete(self, _isolate_state_file):
        mark_phase_complete("prerequisites")
        assert is_phase_complete("prerequisites")

    def test_vault_phase_complete(self, _isolate_state_file):
        mark_phase_complete("vault", "work")
        assert is_phase_complete("vault", "work")
        assert not is_phase_complete("vault", "personal")


class TestResetState:
    """Tests for reset_state function."""

    def test_reset_removes_file(self, _isolate_state_file):
        mark_phase_complete("prerequisites")
        assert _isolate_state_file.exists()
        reset_state()
        assert not _isolate_state_file.exists()

    def test_reset_missing_file_ok(self, _isolate_state_file):
        reset_state()  # Should not raise


class TestPhases:
    """Tests for phase constants."""

    def test_phases_are_defined(self):
        assert "prerequisites" in PHASES
        assert "claude_mem" in PHASES
        assert "vault" in PHASES
        assert "mcp_config" in PHASES
        assert "verify" in PHASES