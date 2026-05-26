"""Phase 1: Install and configure claude-mem (global, one-time)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from obsiforge.utils.llm_providers import (
    PROVIDERS,
    configure_provider,
    is_provider_configured,
    load_claude_mem_settings,
    validate_api_key,
)
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

CLAUDE_MEM_NPM_PACKAGE = "claude-mem"


def _install_claude_mem_via_npx(provider: str = "") -> bool:
    """Install claude-mem via npx (npm package runner).

    Uses `npx claude-mem install --provider <provider>` which downloads,
    bootstraps the plugin, and configures the LLM provider in one step.
    Works on macOS, Linux, and Windows (requires Node.js >= 18).

    Args:
        provider: LLM provider id ("gemini", "openrouter", "claude").
            If empty, installs without provider flag (user configures later).

    Returns:
        True if installation succeeded.
    """
    cmd = ["npx", CLAUDE_MEM_NPM_PACKAGE, "install", "--yes"]
    if provider:
        cmd.extend(["--provider", provider])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            return True
        print_warning(f"npx claude-mem install exited with code {proc.returncode}")
        if proc.stderr:
            console.print(f"[dim]  {proc.stderr[:200]}[/dim]")
        return False
    except FileNotFoundError:
        print_warning("npx not found — Node.js may not be installed")
        return False
    except subprocess.TimeoutExpired:
        print_warning("npx claude-mem install timed out (120s)")
        return False


def _select_provider(gemini_key: str = "", non_interactive: bool = False) -> dict[str, Any]:
    """Prompt user to select an LLM provider for claude-mem.

    Only determines which provider to use and optionally collects the API key.
    Does NOT write to settings.json — that happens after npx install completes.

    Args:
        gemini_key: Pre-supplied Gemini API key (from --gemini-key flag).
        non_interactive: If True, use defaults without prompting.

    Returns:
        Dict with: provider (str), api_key (str), success (bool).
    """
    import questionary

    # Check if already configured (and npx install already ran)
    current = is_provider_configured()
    if current["configured"]:
        print_success(f"LLM provider already configured: {current['details']}")
        return {"success": True, "provider": current["provider"], "api_key": "", "skipped": True}

    # If gemini_key provided via CLI flag, use directly
    if gemini_key:
        if not validate_api_key("gemini", gemini_key):
            print_error("Gemini API key format invalid (should start with 'AI')")
            return {
                "success": False, "provider": "gemini",
                "api_key": "", "error": "invalid gemini key",
            }
        print_success("Gemini Flash selected (API key provided via --gemini-key)")
        return {"success": True, "provider": "gemini", "api_key": gemini_key}

    # Non-interactive default: Gemini, but needs key
    if non_interactive:
        print_warning("LLM provider not configured. Run 'obsiforge init' without -y to configure.")
        return {
            "success": False, "provider": "", "api_key": "",
            "error": "no provider configured in non-interactive mode",
        }

    # Interactive selection
    console.print("\n  [bold]Select LLM provider for claude-mem:[/bold]")

    # questionary doesn't render Rich markup, so use plain labels for the menu
    # and print warnings separately
    choice_labels: list[str] = []
    for _pid, info in PROVIDERS.items():
        label: str = info["display_name"]
        choice_labels.append(label)

    default_label: str = PROVIDERS["gemini"]["display_name"]
    selected_label = questionary.select(
        "Which provider?",
        choices=choice_labels,
        default=default_label,
    ).ask()

    if not selected_label:
        return {"success": False, "provider": "", "api_key": "", "error": "no selection"}

    # Map selected label back to provider id
    provider_id = next(
        pid for pid, info in PROVIDERS.items()
        if info["display_name"] == selected_label
    )
    provider_info = PROVIDERS[provider_id]

    if provider_info.get("warning"):
        console.print(f"  [yellow]Note:[/yellow] {provider_info['warning']}")

    # Get API key if needed
    api_key = ""
    if provider_info["needs_api_key"]:
        api_key = questionary.password(
            f"Enter your {provider_id.capitalize()} API key:"
        ).ask()
        if not api_key:
            print_error("API key is required. Skipping provider config.")
            return {
                "success": False, "provider": provider_id,
                "api_key": "", "error": "no api key provided",
            }
        if not validate_api_key(provider_id, api_key):
            print_warning(
                f"Key doesn't match expected format for "
                f"{provider_id}. Setting anyway — verify manually."
            )

    print_success(f"Selected {provider_info['display_name']}")
    return {"success": True, "provider": provider_id, "api_key": api_key}


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


def _create_mcp_sync_hook(hooks_dir: Path) -> Path:
    """Create the mcp-sync.sh hook that syncs MCP credentials on session start."""
    hook_path = hooks_dir / "mcp-sync.sh"
    script = """\
#!/usr/bin/env bash
# ObsiForge: Auto-sync MCP credentials on session start
OBSIFORGE_LOG="${HOME}/.claude/obsiforge-sync.log"

if ! command -v obsiforge &>/dev/null; then
    echo "[$(date -Iseconds)] ERROR: obsiforge not found on PATH" >> "${OBSIFORGE_LOG}"
    exit 0
fi

result=$(obsiforge sync 2>&1)
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "[$(date -Iseconds)] ERROR: sync failed (exit ${exit_code}):" \
         "${result}" >> "${OBSIFORGE_LOG}"
elif [ -n "${result}" ]; then
    echo "[$(date -Iseconds)] INFO: ${result}" >> "${OBSIFORGE_LOG}"
fi
"""
    hook_path.write_text(script, encoding="utf-8")
    hook_path.chmod(0o755)
    return hook_path


def run(
    vault_name: str,
    vault_path: str,
    dry_run: bool = False,
    non_interactive: bool = False,
    gemini_key: str = "",
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

    # Step 1: Determine LLM provider (needed for npx install --provider flag)
    print_step("Selecting LLM provider for claude-mem")
    provider_id = ""
    api_key = ""
    if dry_run:
        current = is_provider_configured()
        if current["configured"]:
            print_dry_run(f"Provider already configured: {current['details']}")
            provider_id = current.get("provider", "")
        else:
            print_dry_run("Would prompt for LLM provider selection and API key")
    else:
        provider_result = _select_provider(gemini_key=gemini_key, non_interactive=non_interactive)
        provider_id = provider_result.get("provider", "")
        api_key = provider_result.get("api_key", "")
        if not provider_result.get("success"):
            print_warning(
                "claude-mem will run but observation generation "
                "may fail without an LLM provider."
            )
            print_warning("Configure manually: edit ~/.claude-mem/settings.json")

    # Step 2: Install claude-mem (with --provider flag if known)
    if mem_path and mem_path.exists():
        print_success(f"claude-mem already installed at {mem_path}")
        result["mem_installed"] = True
    else:
        print_step("Installing claude-mem plugin")
        if dry_run:
            print_dry_run(f"Would install claude-mem via npx (provider: {provider_id or 'none'})")
        else:
            # npx claude-mem install --provider <id> (cross-platform)
            success = _install_claude_mem_via_npx(provider=provider_id)
            if success:
                print_success("claude-mem plugin installed via npx")
                result["mem_installed"] = True
                mem_path = get_claude_mem_path()
            else:
                # Fallback to Claude Code CLI
                print_step("npx install failed, trying Claude Code CLI")
                try:
                    proc = subprocess.run(
                        ["claude", "plugin", "install", "claude-mem"],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if proc.returncode == 0:
                        print_success("claude-mem plugin installed via CLI")
                        result["mem_installed"] = True
                        mem_path = get_claude_mem_path()
                    else:
                        print_warning(f"claude-mem install may have failed: {proc.stderr}")
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    print_error(f"Failed to install claude-mem: {e}")
                    print_warning("Install manually: npx claude-mem install --yes")

    # Step 2.5: Write API key to claude-mem settings (after install to avoid overwrite)
    # npx install sets the provider but not the API key (it skips in non-TTY mode)
    if provider_id and api_key and not dry_run:
        key_result = configure_provider(provider_id, api_key=api_key)
        if key_result.get("success"):
            provider_info = PROVIDERS.get(provider_id)
            display = provider_info["display_name"] if provider_info else provider_id
            print_success(f"API key configured for {display}")
        else:
            print_warning(f"Failed to write API key: {key_result.get('error', 'unknown')}")
    elif (
        provider_id
        and not api_key
        and provider_id in PROVIDERS
        and PROVIDERS[provider_id]["needs_api_key"]
        and not dry_run
    ):
        # Provider selected but no key collected (e.g., Anthropic doesn't need one)
        pass
    result["provider_configured"] = is_provider_configured().get("configured", False)

    # Step 3: Create consolidate-reminder hook
    print_step("Creating consolidate-reminder hook")
    if dry_run:
        print_dry_run(f"Would create hook at {hooks_dir / 'consolidate-reminder.js'}")
    else:
        hook_path = _create_consolidate_hook(hooks_dir)
        print_success(f"Hook created at {hook_path}")

    # Step 3b: Create mcp-sync hook
    print_step("Creating mcp-sync hook")
    mcp_sync_path = hooks_dir / "mcp-sync.sh"
    if dry_run:
        print_dry_run(f"Would create hook at {mcp_sync_path}")
    else:
        _create_mcp_sync_hook(hooks_dir)
        print_success(f"Hook created at {mcp_sync_path}")

    # Step 4: Merge into settings.json
    print_step("Configuring settings.json")

    # Build the merge data
    mem_server_path = mem_path or Path(
        "~/.claude/plugins/marketplaces/thedotmack/plugin/scripts/mcp-server.cjs"
    )

    mem_worker_port = int(
        load_claude_mem_settings().get("CLAUDE_MEM_WORKER_PORT", CLAUDE_MEM_WORKER_PORT)
    )

    merge_data: dict[str, Any] = {
        "env": {
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        },
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": "npx claude-mem start"},
                        {"type": "command", "command": f"bash {mcp_sync_path}"},
                    ],
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

    # Step 5: Add enabledPlugins
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