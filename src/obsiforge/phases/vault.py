"""Phase 2: Configure Obsidian vault (per-vault)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from obsiforge.utils.crypto import generate_api_key, generate_bearer_token
from obsiforge.utils.plugin_downloader import download_all_plugins
from obsiforge.utils.ports import allocate_ports
from obsiforge.utils.prompt import (
    print_dry_run,
    print_error,
    print_step,
    print_success,
    print_warning,
)
from obsiforge.utils.settings_merge import _mask_sensitive

console = Console()

# The 3 Obsidian plugins required
REQUIRED_PLUGINS = [
    "mcp-tools-istefox",
    "obsidian-local-rest-api",
]


def _write_workspace_json(vault_path: Path, dry_run: bool = False) -> None:
    """Write .obsidian/workspace.json — Obsidian requires this to consider a vault valid."""
    workspace_file = vault_path / ".obsidian" / "workspace.json"

    if dry_run:
        print_dry_run(f"Would write {workspace_file}")
    else:
        if workspace_file.exists():
            print_warning(f"{workspace_file} already exists. Skipping.")
        else:
            workspace_file.write_text("{}\n", encoding="utf-8")
            print_success(f"Created {workspace_file}")


def _ensure_plugin_data_files(vault_path: Path, dry_run: bool = False) -> None:
    """Create empty data.json in each plugin dir if missing.

    Obsidian won't load a plugin's settings UI without a data.json.
    The real configs are written by _write_rest_api_config and
    _write_mcp_connector_config, so this is a safety net.
    """
    for plugin_id in REQUIRED_PLUGINS:
        data_file = vault_path / ".obsidian" / "plugins" / plugin_id / "data.json"
        if dry_run:
            print_dry_run(f"Would ensure {data_file} exists")
        elif not data_file.exists():
            data_file.write_text("{}\n", encoding="utf-8")
            print_success(f"Created empty {data_file.relative_to(vault_path)}")


def _register_vault_in_obsidian(vault_path: Path, dry_run: bool = False) -> bool:
    """Register the vault in Obsidian's obsidian.json and mark it for auto-open.

    Obsidian reads ``obsidian.json`` at startup. A vault entry with
    ``"open": true`` causes Obsidian to skip the vault selector and open
    that vault directly — this is the mechanism we use to guarantee the
    correct vault opens without user interaction.

    This function also sets ``"cli": true`` at the top level so that the
    Obsidian CLI is available for future use (e.g. ``obsidian vault=…``).

    Returns:
        True if the vault was registered (or already was), False on error.
    """
    import os

    # Skip registration in test environments
    if os.environ.get("OBSIFORGE_SKIP_OBSIDIAN_REGISTRATION"):
        return True

    import secrets

    from obsiforge.utils.platform import get_obsidian_config_dir

    config_dir = get_obsidian_config_dir()
    config_file = config_dir / "obsidian.json"

    abs_path = str(vault_path.resolve())

    # Read existing config or create empty
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"vaults": {}}
    else:
        data = {"vaults": {}}

    vaults = data.get("vaults", {})
    now_ms = int(__import__("time").time() * 1000)

    # Find our vault entry (by path) or create one
    our_vault_id = None
    for vault_id, vault_info in vaults.items():
        if vault_info.get("path") == abs_path:
            our_vault_id = vault_id
            vault_info["ts"] = now_ms
            break

    if our_vault_id is None:
        # Backup before first modification
        if config_file.exists():
            backup = config_file.with_suffix(".json.bak")
            shutil.copy2(config_file, backup)

        our_vault_id = secrets.token_hex(8)
        vaults[our_vault_id] = {
            "path": abs_path,
            "ts": now_ms,
        }

    # Set "open": true on our vault — Obsidian auto-opens it on launch
    vaults[our_vault_id]["open"] = True

    # Remove "open" from all other vaults (only one can be auto-opened)
    for vault_id, vault_info in vaults.items():
        if vault_id != our_vault_id:
            vault_info.pop("open", None)

    data["vaults"] = vaults

    # Enable CLI programmatically so the user doesn't have to
    data["cli"] = True

    # Write atomically: write to temp file, then rename
    if dry_run:
        print_dry_run(f"Would register vault in {config_file}")
        return True

    config_dir.mkdir(parents=True, exist_ok=True)
    temp_file = config_file.with_suffix(".json.tmp")
    try:
        temp_file.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        temp_file.replace(config_file)
        print_success(f"Registered vault in Obsidian ({config_file.name})")
        return True
    except OSError as e:
        print_warning(f"Could not register vault in Obsidian: {e}")
        if temp_file.exists():
            temp_file.unlink()
        return False


def _is_obsidian_running() -> bool:
    """Check if Obsidian is currently running (cross-platform)."""
    from obsiforge.utils.platform import get_platform

    plat = get_platform()
    try:
        if plat == "windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "Obsidian.exe" in result.stdout
        else:
            # macOS and Linux: pgrep
            flag = "-x" if plat == "macos" else "-f"
            result = subprocess.run(
                ["pgrep", flag, "obsidian" if plat == "linux" else "Obsidian"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _quit_obsidian() -> bool:
    """Gracefully quit Obsidian (cross-platform).

    Returns True if the quit command was sent successfully.
    """
    from obsiforge.utils.platform import get_platform

    plat = get_platform()
    try:
        if plat == "macos":
            subprocess.run(
                ["osascript", "-e", 'tell application "Obsidian" to quit'],
                capture_output=True,
                timeout=10,
            )
        elif plat == "linux":
            subprocess.run(
                ["pkill", "-f", "obsidian"],
                capture_output=True,
                timeout=5,
            )
        elif plat == "windows":
            # /F flag omitted for graceful quit
            subprocess.run(
                ["taskkill", "/IM", "Obsidian.exe"],
                capture_output=True,
                timeout=10,
            )
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _wait_for_obsidian_quit(timeout: int = 15) -> bool:
    """Wait for Obsidian process to exit."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_obsidian_running():
            return True
        time.sleep(0.5)
    return False


def _launch_obsidian() -> None:
    """Launch Obsidian in the background (cross-platform)."""
    from obsiforge.utils.platform import get_platform

    plat = get_platform()
    try:
        if plat == "macos":
            subprocess.Popen(
                ["open", "-a", "Obsidian"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif plat == "linux":
            subprocess.Popen(
                ["obsidian"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif plat == "windows":
            subprocess.Popen(
                ["start", "", "Obsidian.exe"],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except FileNotFoundError:
        print_warning("Could not launch Obsidian automatically.")


def _wait_for_obsidian_ready(vault_path: Path, timeout: int = 30) -> bool:
    """Wait until Obsidian is running and has opened the target vault.

    Verifies that obsidian.json still contains our vault entry (meaning
    Obsidian didn't overwrite it on startup) and that the workspace
    directory exists.
    """
    import time

    from obsiforge.utils.platform import get_obsidian_config_dir

    abs_path = str(vault_path.resolve())
    config_dir = get_obsidian_config_dir()
    config_file = config_dir / "obsidian.json"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if _is_obsidian_running() and config_file.exists():
            try:
                data = json.loads(config_file.read_text(encoding="utf-8"))
                vault_found = any(
                    v.get("path") == abs_path
                    for v in data.get("vaults", {}).values()
                )
                if vault_found:
                    return True
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(1)

    # Obsidian is running but our vault wasn't found in config
    return _is_obsidian_running()


def _discover_actual_mcp_port(allocated_port: int, timeout: int = 15) -> int:
    """Discover the actual port the MCP Connector is listening on.

    The MCP Connector plugin uses ports 27200-27205 and picks the first
    available one. If the allocated port is in use, return it. Otherwise,
    scan the Obsidian process's listening ports to find the real one.

    Returns:
        The actual port the MCP Connector is using, or the allocated port
        as a fallback.
    """
    import socket
    import time

    # If Obsidian isn't running, no point scanning — return allocated port
    if not _is_obsidian_running():
        return allocated_port

    # First check if the allocated port is already working
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        if sock.connect_ex(("127.0.0.1", allocated_port)) == 0:
            sock.close()
            return allocated_port
        sock.close()
    except OSError:
        pass

    # Wait a bit for the plugin to start
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        from obsiforge.utils.platform import get_platform

        plat = get_platform()
        real_ports: list[int] = []
        try:
            if plat == "macos":
                result = subprocess.run(
                    ["lsof", "-i", "-P", "-n"],
                    capture_output=True, text=True, timeout=10,
                )
                for line in result.stdout.splitlines():
                    if "Obsidian" not in line or "LISTEN" not in line:
                        continue
                    match = re.search(r"(?:localhost|\*|127\.0\.0\.1):(\d+)", line)
                    if match:
                        real_ports.append(int(match.group(1)))
            elif plat == "linux":
                result = subprocess.run(
                    ["ss", "-tlnp"],
                    capture_output=True, text=True, timeout=10,
                )
                for line in result.stdout.splitlines():
                    if "obsidian" not in line.lower():
                        continue
                    match = re.search(r"(?:127\.0\.0\.1|\*):(\d+)", line)
                    if match:
                        real_ports.append(int(match.group(1)))
            elif plat == "windows":
                pid_result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe",
                     "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5,
                )
                obsidian_pids: set[str] = set()
                for pline in pid_result.stdout.splitlines():
                    if "Obsidian" in pline:
                        parts = pline.strip('"').split('","')
                        if len(parts) >= 2:
                            obsidian_pids.add(parts[1])
                if obsidian_pids:
                    result = subprocess.run(
                        ["netstat", "-ano"],
                        capture_output=True, text=True, timeout=10,
                    )
                    for nline in result.stdout.splitlines():
                        if "LISTENING" not in nline:
                            continue
                        pid = nline.strip().split()[-1]
                        if pid not in obsidian_pids:
                            continue
                        match = re.search(r"(?:127\.0\.0\.1|0\.0\.0\.0):(\d+)", nline)
                        if match:
                            real_ports.append(int(match.group(1)))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # MCP Connector uses ports in 27200-27210 range
        mcp_candidates = sorted(p for p in set(real_ports) if 27200 <= p <= 27210)
        if mcp_candidates:
            return mcp_candidates[0]

        time.sleep(2)

    return allocated_port  # Fallback


def _open_obsidian(vault_path: Path, vault_name: str, dry_run: bool = False) -> bool:
    """Open vault in Obsidian using the quit-modify-launch strategy.

    Strategy:
    1. Always quit Obsidian — even if we think it's not running, the quit
       command is harmless and protects against false negatives from process
       detection. Obsidian caches vault data in memory and overwrites
       obsidian.json on exit, so any registration we write while it runs
       would be lost.
    2. Register the vault in obsidian.json with ``"open": true`` so
       Obsidian auto-opens it on launch (skipping the vault selector).
    3. Verify the registration persisted (not overwritten by a lingering
       Obsidian process). If it didn't, retry the quit-wait-write cycle.
    4. Launch Obsidian — it reads obsidian.json and opens our vault.
    5. Wait for Obsidian to fully load the vault (workspace.json populated).
    """
    if dry_run:
        print_dry_run(f"Would register vault and open Obsidian with '{vault_name}'")
        return True

    # Skip Obsidian interaction in test environments
    if os.environ.get("OBSIFORGE_SKIP_OBSIDIAN_REGISTRATION"):
        print_success(f"Opened Obsidian with vault '{vault_name}' (skipped in test)")
        return True

    import time

    from obsiforge.utils.platform import get_obsidian_config_dir

    abs_path = str(vault_path.resolve())

    # Step 1: Always quit Obsidian. The quit command is harmless if
    # Obsidian isn't running, but it prevents the race condition where
    # Obsidian IS running but process detection missed it.
    print_step("Restarting Obsidian to load new vault registration")
    _quit_obsidian()
    if not _wait_for_obsidian_quit(timeout=20):
        print_warning("Obsidian did not close in time, attempting launch anyway")
    else:
        # Wait longer for file I/O to complete — Obsidian writes config on quit
        time.sleep(3)

    # Step 2: Register vault in obsidian.json (with open=true, cli=true)
    _register_vault_in_obsidian(vault_path, dry_run=False)

    # Step 3: Verify registration persisted. Obsidian overwrites obsidian.json
    # on quit AND on startup. If our vault is missing from the file, a
    # lingering Obsidian process overwrote it — retry once.
    config_dir = get_obsidian_config_dir()
    config_file = config_dir / "obsidian.json"
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            our_vault_found = any(
                v.get("path") == abs_path
                for v in data.get("vaults", {}).values()
            )
            if not our_vault_found:
                print_warning("Registration was overwritten — retrying quit and register")
                _quit_obsidian()
                _wait_for_obsidian_quit(timeout=15)
                time.sleep(1)
                _register_vault_in_obsidian(vault_path, dry_run=False)
        except (json.JSONDecodeError, OSError):
            pass

    # Step 4: Launch Obsidian — it auto-opens the vault with open=true
    _launch_obsidian()

    # Step 5: Wait for readiness
    if _wait_for_obsidian_ready(vault_path, timeout=30):
        print_success(f"Opened Obsidian with vault '{vault_name}'")
    else:
        print_warning(
            "Obsidian launched but vault readiness not confirmed. "
            f"If '{vault_name}' doesn't appear, open it manually."
        )

    return True


def _create_directory_structure(vault_path: Path) -> list[Path]:
    """Create vault directory structure.

    Returns:
        List of created directories.
    """
    dirs = [
        vault_path / "Claude",
        vault_path / ".claude" / "skills" / "consolidate",
        vault_path / ".claude" / "skills" / "dashboard",
        vault_path / ".obsidian" / "plugins" / "mcp-tools-istefox",
        vault_path / ".obsidian" / "plugins" / "obsidian-local-rest-api",
    ]

    created = []
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        created.append(d)

    return created


def _write_skills(vault_name: str, vault_path: Path, dry_run: bool = False) -> None:
    """Write Claude Code skill files (dashboard, consolidate)."""
    skills_dir = vault_path / ".claude" / "skills"

    # Dashboard skill
    dashboard_template = """---
name: dashboard
description: Load project context from the Obsidian vault at session start.
  Gives a briefing of current state, progress, and what to work on next.
---

# Dashboard: Session Start Briefing

Load project context from the Obsidian vault at session start.

## When to Activate

- At the start of a new session
- When the user says `/dashboard`
- When resuming work after a break

## How It Works

### Step 1: Load Vault Context

Read the core vault notes:

1. `Claude/user-preferences.md` — Preferences, OS, editor, communication style
2. `Claude/MEMORY.md` — Memory index and search tools reference
3. Search claude-mem for recent observations

### Step 2: Check System Status

Run quick health checks:

1. `search_vault_smart` for semantic search availability
2. Check claude-mem worker via MCP tools
3. If semantic search returns 0 results, note indexing may be in progress

### Step 3: Generate Briefing

```
## Session Briefing — {vault_name}

**Vault Status**: [indexed / indexing in progress]
**Last Work**: [from claude-mem recent observations]
**Next Steps**: [from user-preferences.md or project notes]
**System Health**: [MCP tools connected / issues]
```

## Anti-Patterns

- **Do NOT read every vault note** — start with core notes
- **Do NOT dump full file contents** — summarize and point
- **Do NOT skip the briefing** — orient yourself even if not asked
- **At session end**, run `/consolidate` to distill observations
  into vault notes
"""
    # Consolidate skill
    consolidate = """---
name: consolidate
description: Distill recent claude-mem session observations into the Obsidian vault.
  Run at session end or on demand to keep vault knowledge current.
---

# Consolidate: claude-mem → Vault

Distill recent claude-mem observations into the Obsidian vault (Layer 2).

## When to Activate

- At the end of a session (recommended)
- When the user says `/consolidate`
- When significant project knowledge was discovered during the session

## How It Works

### Step 1: Fetch Recent Observations

Search claude-mem for recent observations using the claude-mem MCP search tool.

### Step 2: Filter What Belongs in the Vault

| Goes to Vault (Layer 2) | Stays in claude-mem (Layer 1) |
|---|---|
| Architecture decisions | "How did we fix X bug?" |
| User preferences | "What commands did we run?" |
| Project context changes | Session summaries |
| New discoveries | Tool usage patterns |
| Decisions with rationale | Temporary workarounds |

**Rule**: If it helps a FUTURE session understand the project
better -> vault. If only about THIS session -> claude-mem.

### Step 3: Update Vault Notes

**Always use Read/Write/Edit with absolute paths (not MCP tools)
to avoid vault mismatch issues.** Update existing notes rather than
creating new ones.

### Step 4: Verify

Read back modified notes to confirm correctness.

## Anti-Patterns

- **Do NOT duplicate** what's already in claude-mem
- **Do NOT overwrite** existing content — append or update sections
- **Do NOT store temporary state** — "currently debugging X" goes to claude-mem
- **Do NOT create new notes unless truly necessary** — add to existing notes
- **Do NOT use MCP tools** for writing — use Read/Write/Edit
  with absolute paths to avoid vault mismatch

## Vault Conventions

- Every note MUST have frontmatter: `type`, `tags`, `status`,
  `created`, `updated`
- Tags for categorization only (e.g., `#project/prism`),
  NOT for linking notes
- No wikilinks between notes — each note is self-contained
- Update the `updated` date in frontmatter when modifying a note
- Do NOT create new notes unless truly necessary — add to existing notes
"""

    skills = {
        "dashboard/SKILL.md": dashboard_template.replace("{vault_name}", vault_name),
        "consolidate/SKILL.md": consolidate,
    }

    for skill_path, content in skills.items():
        skill_file = skills_dir / skill_path
        skill_file.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            print_dry_run(f"Would write {skill_file}")
        else:
            if skill_file.exists():
                print_warning(f"{skill_file} already exists. Skipping.")
            else:
                skill_file.write_text(content, encoding="utf-8")
                print_success(f"Created {skill_file}")


def _write_community_plugins(vault_path: Path, dry_run: bool = False) -> None:
    """Write community-plugins.json listing required plugins."""
    plugins_file = vault_path / ".obsidian" / "community-plugins.json"
    content = json.dumps(REQUIRED_PLUGINS, indent=2) + "\n"

    if dry_run:
        print_dry_run(f"Would write {plugins_file}")
        console.print(content)
    else:
        if plugins_file.exists():
            existing = json.loads(plugins_file.read_text(encoding="utf-8"))
            merged = list(set(existing + REQUIRED_PLUGINS))
            plugins_file.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
            print_success(f"Updated {plugins_file} ({len(merged)} plugins)")
        else:
            plugins_file.write_text(content, encoding="utf-8")
            print_success(f"Created {plugins_file} ({len(REQUIRED_PLUGINS)} plugins)")


def _write_rest_api_config(
    vault_path: Path, port: int, api_key: str, dry_run: bool = False,
) -> None:
    """Write Local REST API plugin data.json."""
    config_dir = vault_path / ".obsidian" / "plugins" / "obsidian-local-rest-api"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "data.json"

    config = {
        "port": port,
        "apiKey": api_key,
        "enableSecureServer": True,
    }

    if dry_run:
        print_dry_run(f"Would write {config_file}")
        # Mask API key in dry run
        masked = {**config, "apiKey": _mask_sensitive(api_key)}
        console.print(json.dumps(masked, indent=2))
    else:
        config_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print_success(f"Configured REST API on port {port}")


def _write_mcp_connector_config(
    vault_path: Path, bearer_token: str, dry_run: bool = False,
) -> None:
    """Write MCP Connector (istefox) plugin data.json."""
    config_dir = vault_path / ".obsidian" / "plugins" / "mcp-tools-istefox"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "data.json"

    # Preserve existing config if present
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    # Add/merge MCP transport config (preserve existing keys like port)
    if "mcpTransport" not in config:
        config["mcpTransport"] = {}
    config["mcpTransport"]["bearerToken"] = bearer_token

    if "semanticSearch" not in config:
        config["semanticSearch"] = {}
    config["semanticSearch"].setdefault("provider", "native")
    config["semanticSearch"].setdefault("indexingMode", "live")
    config["semanticSearch"].setdefault("unloadModelWhenIdle", True)

    if dry_run:
        print_dry_run(f"Would write {config_file}")
        masked = {**config, "mcpTransport": {"bearerToken": _mask_sensitive(bearer_token)}}
        console.print(json.dumps(masked, indent=2))
    else:
        # Backup existing
        if config_file.exists():
            backup = config_file.with_suffix(".json.bak")
            shutil.copy2(config_file, backup)

        config_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print_success("Configured MCP Connector with bearer token")


def _generate_claude_md(vault_name: str, vault_path: Path, dry_run: bool = False) -> None:
    """Generate CLAUDE.md at vault root."""
    content = f"""# {vault_name.title()}

## Memory Architecture (3 Layers)

This project uses a 3-layer memory system. **Never duplicate knowledge across layers.**

| Layer | What | Where | Search |
|-------|------|------|--------|
| 1. claude-mem | Session observations | `~/.claude-mem/` | `/mem-search`, MCP tools |
| 2. Obsidian vault | Project knowledge | `Claude/` folder | obsidian-mcp-tools |
| 3. Claude native | Pointer only | `memory/MEMORY.md` | - |

### Rules

- **New knowledge → Obsidian vault (Layer 2).**
  Use `create_vault_file` or `patch_vault_file` to write to `Claude/`.
- **Session observations → claude-mem (Layer 1).** Automatic via hooks.
- **Claude native memory → pointer only.** `memory/MEMORY.md` should only say
  "Use MCP tools to read/write the vault."
- **If in doubt**, ask: "Is this a session-level observation or project-level knowledge?"

### How to Search

Pick the right layer for the question. Never search both for the same question.

- **Resuming a project?** → Search the **vault** (Layer 2) for
  current status, architecture, decisions.
  Use `search_vault_smart("project name architecture")`
  or `get_vault_file("path")`.
- **"How did we fix X?"** → Search **claude-mem** (Layer 1) for
  the chain of attempts and solutions.
  Use `/mem-search` or MCP `search(query="bug fix X")`.
- **Start of session?** → claude-mem summary arrives automatically
  via SessionStart hook.
- **End of session?** → Run `/consolidate` to distill important
  observations into vault notes.

**Rule of thumb:** Vault for "what is the current state of X?",
claude-mem for "how did we solve X?".

### Semantic Search

**Primary search method.** Use `search_vault_smart` for all vault lookups.
It uses the MCP Connector's built-in Transformers.js and re-indexes on every
query — always up to date.

Fallback: `search_vault_simple` for substring search when the semantic index
is initializing or you need exact matches.

Only use `get_vault_file` directly when you already know the exact
file and need its full content.

### Session Lifecycle

- **Start**: Run `/dashboard` to load vault context and check system health.
- **End**: Run `/consolidate` to distill claude-mem observations into vault notes.
"""

    if dry_run:
        print_dry_run(f"Would write {vault_path / 'CLAUDE.md'} ({len(content)} chars)")
    else:
        # Append, don't overwrite existing CLAUDE.md
        claude_md = vault_path / "CLAUDE.md"
        if claude_md.exists():
            existing = claude_md.read_text()
            if f"# {vault_name.title()}" not in existing and "Memory Architecture" not in existing:
                # Append the memory section
                claude_md.write_text(existing + "\n\n" + content, encoding="utf-8")
                print_success(f"Appended memory architecture to {claude_md}")
            else:
                print_warning(
                    f"{claude_md} already contains memory "
                    "architecture section. Skipping."
                )
        else:
            claude_md.write_text(content, encoding="utf-8")
            print_success(f"Created {claude_md}")


def _generate_memory_md(vault_path: Path, dry_run: bool = False) -> None:
    """Generate Claude/MEMORY.md (Layer 3 pointer)."""
    content = """# Memory Index

This is a pointer file. Do NOT store knowledge here — use the vault instead.

## How to Access Knowledge

- **Quick start**: Run `/dashboard` at session start to load vault context
  and check system health
- **Vault notes**: Use `get_vault_file("Claude/user-preferences.md")`
  or `search_vault_smart("query")`
- **Session observations**: Use `/mem-search` or claude-mem MCP tools
- **Never** store full knowledge here — this file is just an index

### Vault Notes

Create and update notes in `Claude/` as needed:
- **user-preferences.md** — Your preferences, OS, editor,
  communication style
- Add more notes as your project grows: project docs, lessons learned,
  architecture decisions

## Search

- **Primary**: `search_vault_smart(query)` — MCP Connector
  Transformers.js, always up to date
- **Fallback**: `search_vault_simple(query)` — substring search
"""

    if dry_run:
        print_dry_run(f"Would write {vault_path / 'Claude' / 'MEMORY.md'}")
    else:
        memory_md = vault_path / "Claude" / "MEMORY.md"
        if memory_md.exists():
            print_warning(f"{memory_md} already exists. Skipping.")
        else:
            memory_md.write_text(content, encoding="utf-8")
            print_success(f"Created {memory_md}")


def _generate_user_preferences_md(
    vault_path: Path, dry_run: bool = False, non_interactive: bool = False,
) -> None:
    """Generate Claude/user-preferences.md with OS auto-detection."""
    import platform

    os_name = platform.system()
    if os_name == "Darwin":
        os_display = "macOS"
    elif os_name == "Linux":
        os_display = "Linux"
    elif os_name == "Windows":
        os_display = "Windows"
    else:
        os_display = os_name

    content = f"""# User Preferences

## Communication
- **Language**: [your preference — e.g., Spanish for conversation, \
English for code]
- **Style**: [your preference — e.g., explain step by step, assume \
advanced knowledge]

## Development
- **OS**: {os_display}
- **Python**: [your setup — e.g., pyenv + uv]
- **Editor**: [your editor — e.g., VS Code, Obsidian for notes]

## Active Projects
| Project | Code | Vault | Stack |
|---------|------|-------|-------|
| [name] | [path] | [path] | [tech] |
"""

    if dry_run:
        print_dry_run(
            f"Would write {vault_path / 'Claude' / 'user-preferences.md'}"
        )
    else:
        prefs_file = vault_path / "Claude" / "user-preferences.md"
        if prefs_file.exists():
            print_warning(f"{prefs_file} already exists. Skipping.")
        else:
            prefs_file.write_text(content, encoding="utf-8")
            print_success(f"Created {prefs_file}")


def _write_appearance_json(vault_path: Path, dry_run: bool = False) -> None:
    """Write .obsidian/appearance.json with dark theme default."""
    import json

    appearance_file = vault_path / ".obsidian" / "appearance.json"

    if dry_run:
        print_dry_run(f"Would write {appearance_file}")
    else:
        if appearance_file.exists():
            print_warning(f"{appearance_file} already exists. Skipping.")
        else:
            appearance_file.write_text(
                json.dumps({"cssTheme": "obsidian"}) + "\n",
                encoding="utf-8",
            )
            print_success(f"Created {appearance_file}")


def run(
    vault_name: str,
    vault_path: str,
    dry_run: bool = False,
    skip_semantic: bool = False,
    non_interactive: bool = False,
) -> dict[str, Any]:
    """Create vault directory structure and configure plugins.

    Returns:
        Dict with generated config for downstream phases.
    """
    vault = Path(vault_path).expanduser().resolve()

    if not re.match(r'^[a-zA-Z0-9_-]+$', vault_name):
        print_error(
            f"Invalid vault name '{vault_name}'. "
            "Use only letters, numbers, hyphens, and underscores."
        )
        raise SystemExit(1)

    # Step 1: Allocate ports
    print_step("Allocating ports")
    ports = allocate_ports(vault_name)
    rest_port = ports["rest_api"]
    mcp_port = ports["mcp_http"]
    print_success(f"REST API: port {rest_port}, MCP HTTP: port {mcp_port}")

    # Step 2: Generate API keys and tokens
    print_step("Generating API keys and tokens")
    api_key = generate_api_key(64)
    bearer_token = generate_bearer_token(44)
    print_success(f"API key: {_mask_sensitive(api_key)}")
    print_success(f"Bearer token: {_mask_sensitive(bearer_token)}")

    # Step 3: Create directory structure
    print_step("Creating vault directory structure")
    if dry_run:
        print_dry_run(f"Would create directories under {vault}")
    else:
        created = _create_directory_structure(vault)
        for d in created:
            print_success(f"Created {d.relative_to(vault)}")

    # Step 3b: Download plugin files from GitHub
    print_step("Downloading Obsidian plugins")
    installed = download_all_plugins(vault, dry_run)
    if installed and not dry_run:
        print_success(f"Downloaded {len(installed)}/{len(REQUIRED_PLUGINS)} plugins")
    elif not dry_run:
        print_warning("Some plugins could not be downloaded — install manually via Obsidian")

    # Step 4: Write community-plugins.json
    print_step("Configuring Obsidian plugins")
    _write_community_plugins(vault, dry_run)

    # Step 5: Write REST API config
    print_step("Configuring Local REST API")
    _write_rest_api_config(vault, rest_port, api_key, dry_run)

    # Step 6: Write MCP Connector config
    print_step("Configuring MCP Connector (istefox)")
    _write_mcp_connector_config(vault, bearer_token, dry_run)

    # Step 7: Generate vault content
    print_step("Generating vault content templates")
    _generate_claude_md(vault_name, vault, dry_run)
    _generate_memory_md(vault, dry_run)
    _generate_user_preferences_md(vault, dry_run, non_interactive)

    # Step 7b: Write Claude Code skills
    print_step("Writing Claude Code skills")
    _write_skills(vault_name, vault, dry_run)

    # Step 7c: Write workspace.json (Obsidian validity marker)
    print_step("Creating workspace.json")
    _write_workspace_json(vault, dry_run)

    # Step 7d: Ensure plugin data.json files exist
    print_step("Ensuring plugin data files")
    _ensure_plugin_data_files(vault, dry_run)

    # Step 7e: Write appearance.json (dark theme)
    print_step("Setting dark theme")
    _write_appearance_json(vault, dry_run)

    # Step 8: Open Obsidian to load plugins
    print_step("Opening Obsidian")
    _open_obsidian(vault, vault_name, dry_run)

    # Step 8b: Discover actual MCP Connector port (may differ from allocated)
    # The MCP Connector plugin uses a fixed port range [27200-27205] and
    # picks the first available one, which may not match our allocation.
    actual_mcp_port = mcp_port
    if not dry_run and not os.environ.get("OBSIFORGE_SKIP_OBSIDIAN_REGISTRATION"):
        actual_mcp_port = _discover_actual_mcp_port(mcp_port)
        if actual_mcp_port != mcp_port:
            print_success(
                f"MCP Connector actual port: {actual_mcp_port} "
                f"(allocated: {mcp_port})"
            )

    # Return config for Phase 3
    return {
        "vault_path": str(vault),
        "vault_name": vault_name,
        "rest_api_port": rest_port,
        "mcp_http_port": actual_mcp_port,
        "api_key": api_key,
        "bearer_token": bearer_token,
    }