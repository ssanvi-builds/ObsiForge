"""Safe JSON merge for ~/.claude/settings.json and other config files.

Core principle: NEVER overwrite, only add. If a key already exists with the
same value, skip silently. If it exists with a different value, warn the user.

All writes are atomic: write to .tmp, validate JSON, then rename.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base. Lists are extended, dicts merged.

    Never overwrites existing scalar values — only adds new keys.
    """
    result: dict[str, Any] = {}
    for key in base:
        if isinstance(base[key], list):
            result[key] = list(base[key])  # shallow copy to avoid mutating input
        elif isinstance(base[key], dict):
            result[key] = dict(base[key])  # shallow copy
        else:
            result[key] = base[key]
    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif isinstance(result[key], list) and isinstance(value, list):
            # Extend list, avoiding duplicates
            existing_ids = {json.dumps(item, sort_keys=True) for item in result[key]}
            for item in value:
                if json.dumps(item, sort_keys=True) not in existing_ids:
                    result[key].append(item)
                    existing_ids.add(json.dumps(item, sort_keys=True))
        # If key exists with same value, skip silently
        elif result[key] == value:
            pass
        # If key exists with different value, keep existing (conservative)
    return result


def mask_sensitive(value: str) -> str:
    """Mask sensitive values for display. Shows first 8 + last 4 chars."""
    if len(value) <= 12:
        return value[:4] + "..." + value[-4:]
    return value[:8] + "..." + value[-4:]


# Backward compatibility alias — remove after vault.py migrates
_mask_sensitive = mask_sensitive


def atomic_write_json(path: Path, data: dict[str, Any], backup: bool = True) -> None:
    """Write JSON data atomically with optional backup.

    Args:
        path: Target file path.
        data: Data to write.
        backup: If True, copy original to .bak before writing.
    """
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        if backup_path.exists():
            console.print(f"[dim]Overwriting existing backup: {backup_path}[/dim]")
        shutil.copy2(path, backup_path)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        # Validate the written JSON
        json.loads(tmp_path.read_text(encoding="utf-8"))
        # Use os.replace for cross-platform atomic rename (Path.rename
        # fails on Windows when the target already exists)
        os.replace(tmp_path, path)
    except (json.JSONDecodeError, OSError) as e:
        tmp_path.unlink(missing_ok=True)
        msg = f"Failed to write {path}: {e}"
        raise RuntimeError(msg) from e


def merge_into_settings(
    settings_path: Path,
    merge_data: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Safely merge data into a JSON settings file.

    Never overwrites existing keys with different values. Only adds new keys
    and extends lists. Creates the file if it doesn't exist.

    Args:
        settings_path: Path to the JSON settings file.
        merge_data: Data to merge in.
        dry_run: If True, show what would change without modifying the file.

    Returns:
        The resulting merged data.
    """
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            console.print(
                f"[red]Error:[/red] {settings_path} contains "
                "invalid JSON. Aborting merge."
            )
            msg = f"Invalid JSON in {settings_path}"
            raise ValueError(msg) from None
    else:
        existing = {}
        settings_path.parent.mkdir(parents=True, exist_ok=True)

    merged = _deep_merge(existing, merge_data)

    # Show what changed
    changes = _diff_settings(existing, merged)
    if changes:
        for key, change_type, detail in changes:
            if change_type == "added":
                console.print(f"  [green]+[/green] {key}: {detail}")
            elif change_type == "extended":
                console.print(f"  [green]+[/green] {key}: appended {detail}")
            elif change_type == "exists":
                console.print(f"  [dim]~ {key}: already exists[/dim]")

    if dry_run:
        console.print("[dim]DRY RUN: No changes written.[/dim]")
        return merged

    atomic_write_json(settings_path, merged)
    return merged


def _diff_settings(
    old: dict[str, Any], new: dict[str, Any], prefix: str = ""
) -> list[tuple[str, str, str]]:
    """Compare old and new settings, returning a list of changes.

    Returns list of (key_path, change_type, detail) tuples.
    """
    changes: list[tuple[str, str, str]] = []

    for key in set(list(old.keys()) + list(new.keys())):
        key_path = f"{prefix}.{key}" if prefix else key
        old_val = old.get(key)
        new_val = new.get(key)

        if key not in old:
            changes.append((key_path, "added", _format_value(new_val)))
        elif old_val != new_val:
            if isinstance(old_val, list) and isinstance(new_val, list):
                added = [item for item in new_val if item not in old_val]
                if added:
                    changes.append((key_path, "extended", f"{len(added)} item(s)"))
            elif isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.extend(_diff_settings(old_val, new_val, key_path))
            # Scalar values that differ: keep existing, don't overwrite

    return changes


def _format_value(value: Any) -> str:
    """Format a value for display, masking sensitive strings."""
    if isinstance(value, str) and len(value) > 20:
        # Likely a token/key — mask it
        return mask_sensitive(value)
    if isinstance(value, dict):
        return f"({len(value)} keys)"
    if isinstance(value, list):
        return f"({len(value)} items)"
    return str(value)