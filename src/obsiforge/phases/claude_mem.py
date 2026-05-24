"""Phase 1: Install and configure claude-mem (global, one-time)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from obsiforge.utils.platform import get_claude_config_dir, get_claude_mem_path
from obsiforge.utils.ports import CLAUDE_MEM_WORKER_PORT
from obsiforge.utils.prompt import (
    print_dry_run,
    print_error,
    print_step,
    print_success,
    print_warning,
)
from obsiforge.utils.settings_merge import merge_into_settings

console = Console()


def _create_consolidate_hook(hooks_dir: Path) -> Path:
    """Create the consolidate-reminder hook script (Node.js, cross-platform).

    Args:
        hooks_dir: Directory to create the hook in (~/.claude/hooks/).

    Returns:
        Path to the created hook script.
    """
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "consolidate-reminder.js"

    script = """#!/usr/bin/env node
// ObsiForge: Auto-consolidation reminder at session end
const fs = require('fs');
const path = require('path');
const home = process.env.HOME || process.env.USERPROFILE;
const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

// Try to find vault path from .mcp.json
let vaultPath = '';
try {
  const mcpPath = path.join(projectDir, '.mcp.json');
  if (fs.existsSync(mcpPath)) {
    const mcp = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
    const servers = mcp.mcpServers || {};
    for (const [name, config] of Object.entries(servers)) {
      if (config.env && config.env.SMART_VAULT_PATH) {
        vaultPath = config.env.SMART_VAULT_PATH;
        break;
      }
    }
  }
} catch (e) { console.error('[consolidate-reminder] Error reading .mcp.json:', e.message); }

if (!vaultPath) {
  try {
    const settingsPath = path.join(home, '.claude', 'settings.json');
    const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    const servers = settings.mcpServers || {};
    for (const [name, config] of Object.entries(servers)) {
      if (config.env && config.env.SMART_VAULT_PATH) {
        vaultPath = config.env.SMART_VAULT_PATH;
        break;
      }
    }
  } catch (e) { console.error('[consolidate-reminder] Error reading settings.json:', e.message); }
}

if (vaultPath && fs.existsSync(vaultPath)) {
  const claudeDir = path.join(vaultPath, 'Claude');
  let fileCount = 0;
  try { fileCount = fs.readdirSync(claudeDir)
    .filter(f => f.endsWith('.md')).length; } catch (e) { /* directory may not exist yet */ }
  console.log(`[consolidate-reminder] Session ending. `
    + `Run /consolidate to distill observations into vault: ${vaultPath}`);
  console.log(`[consolidate-reminder] Vault notes: ${fileCount} files available`);
} else {
  console.log('[consolidate-reminder] No Obsidian vault detected. '
    + 'Run /consolidate if working in a project with a vault.');
}
"""
    hook_path.write_text(script, encoding="utf-8")
    hook_path.chmod(0o755)
    return hook_path


def run(
    vault_name: str,
    vault_path: str,
    dry_run: bool = False,
    non_interactive: bool = False,
) -> dict[str, Any]:
    """Install claude-mem plugin and configure global settings.

    Returns:
        Dict with paths and config for downstream phases.
    """
    config_dir = get_claude_config_dir()
    settings_path = config_dir / "settings.json"
    hooks_dir = config_dir / "hooks"
    mem_path = get_claude_mem_path()

    result = {
        "settings_path": str(settings_path),
        "hooks_dir": str(hooks_dir),
        "mem_installed": False,
    }

    # Step 1: Check if claude-mem is already installed
    if mem_path and mem_path.exists():
        print_success(f"claude-mem already installed at {mem_path}")
        result["mem_installed"] = True
    else:
        print_step("Installing claude-mem plugin")
        if dry_run:
            print_dry_run("Would run: claude plugin install claude-mem")
        else:
            try:
                proc = subprocess.run(
                    ["claude", "plugin", "install", "claude-mem"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if proc.returncode == 0:
                    print_success("claude-mem plugin installed")
                    result["mem_installed"] = True
                    # Re-check path after install
                    mem_path = get_claude_mem_path()
                else:
                    print_warning(f"claude-mem install may have failed: {proc.stderr}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                print_error(f"Failed to install claude-mem: {e}")
                print_warning("You can install it manually: claude plugin install claude-mem")

    # Step 2: Create consolidate-reminder hook
    print_step("Creating consolidate-reminder hook")
    if dry_run:
        print_dry_run(f"Would create hook at {hooks_dir / 'consolidate-reminder.js'}")
    else:
        hook_path = _create_consolidate_hook(hooks_dir)
        print_success(f"Hook created at {hook_path}")

    # Step 3: Merge into settings.json
    print_step("Configuring settings.json")

    # Build the merge data
    mem_server_path = mem_path or Path(
        "~/.claude/plugins/marketplaces/thedotmack/plugin/scripts/mcp-server.cjs"
    )

    mem_worker_port = CLAUDE_MEM_WORKER_PORT

    merge_data: dict[str, Any] = {
        "env": {
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        },
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "npx claude-mem start"}],
                }
            ],
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command",
                         "command": f"node {hooks_dir / 'consolidate-reminder.js'}"},
                    ],
                }
            ],
        },
        "mcpServers": {
            "claude-mem": {
                "command": "node",
                "args": [str(mem_server_path)],
                "env": {
                    "CLAUDE_MEM_DATA_DIR": str(Path.home() / ".claude-mem"),
                    "CLAUDE_MEM_WORKER_PORT": str(mem_worker_port),
                },
            }
        },
    }

    if dry_run:
        print_dry_run(f"Would merge into {settings_path}")
        console.print(json.dumps(merge_data, indent=2))
    else:
        merge_into_settings(settings_path, merge_data, dry_run=False)
        print_success(f"Settings merged into {settings_path}")

    # Step 4: Add enabledPlugins
    # Re-read settings fresh to avoid stale data from step 3
    if settings_path.exists():
        try:
            fresh_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            fresh_settings = {}
    else:
        fresh_settings = {}
    enabled_plugins = fresh_settings.get("enabledPlugins", {})
    if "claude-mem@thedotmack" not in enabled_plugins:
        merge_data_plugins = {
            "enabledPlugins": {"claude-mem@thedotmack": True}
        }
        if not dry_run:
            merge_into_settings(settings_path, merge_data_plugins, dry_run=False)
            print_success("claude-mem plugin enabled")

    result["settings_path"] = str(settings_path)
    result["hooks_dir"] = str(hooks_dir)
    return result