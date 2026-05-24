"""Tests for obsiforge.utils.settings_merge module."""

import json
from pathlib import Path

import pytest

from obsiforge.utils.settings_merge import (
    _deep_merge,
    _diff_settings,
    _format_value,
    _mask_sensitive,
    atomic_write_json,
    merge_into_settings,
)


class TestDeepMerge:
    """Tests for _deep_merge function."""

    def test_add_new_key(self):
        result = _deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_same_value_no_change(self):
        result = _deep_merge({"a": 1}, {"a": 1})
        assert result == {"a": 1}

    def test_different_value_keeps_existing(self):
        """Conservative: never overwrite existing scalar values."""
        result = _deep_merge({"a": 1}, {"a": 2})
        assert result == {"a": 1}

    def test_nested_dict_merge(self):
        result = _deep_merge(
            {"mcpServers": {"foo": {"port": 3000}}},
            {"mcpServers": {"bar": {"port": 4000}}},
        )
        assert result == {"mcpServers": {"foo": {"port": 3000}, "bar": {"port": 4000}}}

    def test_list_extend_no_duplicates(self):
        result = _deep_merge(
            {"hooks": {"SessionStart": [{"command": "a"}]}},
            {"hooks": {"SessionStart": [{"command": "b"}, {"command": "a"}]}},
        )
        assert len(result["hooks"]["SessionStart"]) == 2
        assert result["hooks"]["SessionStart"][0]["command"] == "a"
        assert result["hooks"]["SessionStart"][1]["command"] == "b"

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1, "b": {"c": 2}})
        assert result == {"a": 1, "b": {"c": 2}}

    def test_empty_overlay(self):
        result = _deep_merge({"a": 1}, {})
        assert result == {"a": 1}


class TestMaskSensitive:
    """Tests for _mask_sensitive function."""

    def test_long_value_masked(self):
        result = _mask_sensitive("abcdefghijklmnop1234")
        assert result == "abcdefgh...1234"

    def test_short_value_masked(self):
        result = _mask_sensitive("short")
        assert result == "shor...hort" or len(result) < len("short") + 6

    def test_exactly_12_chars(self):
        # 12 chars falls into the short branch (len <= 12)
        result = _mask_sensitive("123456789012")
        assert "..." in result
        assert result.endswith("9012")


class TestAtomicWriteJson:
    """Tests for atomic_write_json function."""

    def test_creates_new_file(self, tmp_path):
        f = tmp_path / "test.json"
        atomic_write_json(f, {"key": "value"})
        assert f.exists()
        assert json.loads(f.read_text()) == {"key": "value"}

    def test_overwrites_existing(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"old": true}')
        atomic_write_json(f, {"new": True}, backup=False)
        data = json.loads(f.read_text())
        assert data == {"new": True}

    def test_creates_backup(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"old": true}')
        atomic_write_json(f, {"new": True}, backup=True)
        backup = f.with_suffix(".json.bak")
        assert backup.exists()
        assert json.loads(backup.read_text()) == {"old": True}

    def test_no_backup_when_flag_false(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"old": true}')
        atomic_write_json(f, {"new": True}, backup=False)
        backup = f.with_suffix(".json.bak")
        assert not backup.exists()


class TestMergeIntoSettings:
    """Tests for merge_into_settings function."""

    def test_creates_new_file(self, tmp_path):
        f = tmp_path / "settings.json"
        result = merge_into_settings(f, {"mcpServers": {"test": {"port": 3000}}})
        assert result["mcpServers"]["test"]["port"] == 3000
        assert f.exists()

    def test_merges_into_existing(self, tmp_path):
        f = tmp_path / "settings.json"
        f.write_text(json.dumps({"existing": "value"}))
        result = merge_into_settings(f, {"new": "entry"})
        assert result["existing"] == "value"
        assert result["new"] == "entry"

    def test_dry_run_does_not_write(self, tmp_path):
        f = tmp_path / "settings.json"
        f.write_text(json.dumps({"existing": "value"}))
        merge_into_settings(f, {"new": "entry"}, dry_run=True)
        data = json.loads(f.read_text())
        assert "new" not in data

    def test_invalid_json_raises(self, tmp_path):
        f = tmp_path / "settings.json"
        f.write_text("not valid json{{{")
        with pytest.raises(ValueError, match="Invalid JSON"):
            merge_into_settings(f, {"key": "val"})


class TestDiffSettings:
    """Tests for _diff_settings function."""

    def test_added_key(self):
        changes = _diff_settings({}, {"new": "value"})
        assert len(changes) == 1
        assert changes[0][1] == "added"

    def test_unchanged_key(self):
        changes = _diff_settings({"a": 1}, {"a": 1})
        assert len(changes) == 0

    def test_list_extension(self):
        changes = _diff_settings(
            {"items": [1]},
            {"items": [1, 2]},
        )
        assert len(changes) == 1
        assert changes[0][1] == "extended"


class TestFormatValue:
    """Tests for _format_value function."""

    def test_short_string(self):
        assert _format_value("short") == "short"

    def test_dict_value(self):
        assert "(2 keys)" in _format_value({"a": 1, "b": 2})

    def test_list_value(self):
        assert "(3 items)" in _format_value([1, 2, 3])