"""Resume-from-state tracking for multi-phase installation.

Tracks which phases have been completed so the installer can resume
after a failure or interruption.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

STATE_DIR = Path.home() / ".claude"
STATE_FILE = STATE_DIR / "obsiforge-state.json"

PHASES = [
    "prerequisites",
    "claude_mem",
    "vault",
    "mcp_config",
    "verify",
]


def load_state() -> dict[str, Any]:
    """Load the current installation state.

    Returns:
        State dict with completed phases and config.
    """
    if not STATE_FILE.exists():
        return {"completed_phases": [], "vaults": {}, "version": "0.1.0"}

    try:
        return dict(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        console.print(f"[yellow]Warning:[/yellow] {STATE_FILE} is corrupted. Starting fresh.")
        return {"completed_phases": [], "vaults": {}, "version": "0.1.0"}


def save_state(state: dict[str, Any]) -> None:
    """Save installation state atomically."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))
        os.replace(tmp, STATE_FILE)
    except (json.JSONDecodeError, OSError) as e:
        tmp.unlink(missing_ok=True)
        msg = f"Failed to save state to {STATE_FILE}: {e}"
        raise RuntimeError(msg) from e


def mark_phase_complete(
    phase: str, vault_name: str | None = None, extra: dict[str, Any] | None = None,
) -> None:
    """Mark a phase as completed.

    Args:
        phase: Phase name (must be one of PHASES).
        vault_name: Optional vault name for per-vault phases.
        extra: Additional data to store for this phase.
    """
    if phase not in PHASES:
        msg = f"Unknown phase: {phase}. Must be one of {PHASES}"
        raise ValueError(msg)

    state = load_state()

    entry = phase
    if vault_name:
        entry = f"{phase}:{vault_name}"

    if entry not in state["completed_phases"]:
        state["completed_phases"].append(entry)

    if extra and vault_name:
        if vault_name not in state["vaults"]:
            state["vaults"][vault_name] = {}
        state["vaults"][vault_name].update(extra)

    save_state(state)


def is_phase_complete(phase: str, vault_name: str | None = None) -> bool:
    """Check if a phase has been completed."""
    state = load_state()
    entry = f"{phase}:{vault_name}" if vault_name else phase
    return entry in state.get("completed_phases", [])


def reset_state() -> None:
    """Remove the state file (for fresh install)."""
    STATE_FILE.unlink(missing_ok=True)