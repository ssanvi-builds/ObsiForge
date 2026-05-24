"""Phase 2: Configure Obsidian vault (per-vault)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

import re

from obsiforge.utils.crypto import generate_api_key, generate_bearer_token
from obsiforge.utils.plugin_downloader import download_all_plugins
from obsiforge.utils.ports import allocate_ports
from obsiforge.utils.settings_merge import _mask_sensitive
from obsiforge.utils.prompt import (
    print_dry_run,
    print_error,
    print_step,
    print_success,
    print_warning,
)

console = Console()

# The 3 Obsidian plugins required
REQUIRED_PLUGINS = [
    "mcp-tools-istefox",
    "obsidian-local-rest-api",
]


def _open_obsidian(vault_path: Path, dry_run: bool = False) -> bool:
    """Open vault in Obsidian app."""
    if dry_run:
        print_dry_run(f"Would open Obsidian with vault {vault_path}")
        return True

    from obsiforge.utils.platform import get_platform

    plat = get_platform()

    try:
        if plat == "macos":
            subprocess.Popen(
                ["open", "-a", "Obsidian", str(vault_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif plat == "linux":
            # Try xdg-open or direct exec
            subprocess.Popen(
                ["obsidian", str(vault_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif plat == "windows":
            subprocess.Popen(
                ["start", "Obsidian.exe", str(vault_path)],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        print_success(f"Opened Obsidian with vault {vault_path.name}")
        return True
    except FileNotFoundError:
        print_warning("Could not open Obsidian automatically. Open it manually.")
        return False


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
description: Load project context from the Obsidian vault at session start. Gives a briefing of current state, progress, and what to work on next.
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

1. `Claude/user.md` — Who I am, preferences, tech environment
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
**Next Steps**: [from user.md or project notes]
**System Health**: [MCP tools connected / issues]
```

## Anti-Patterns

- **Do NOT read every vault note** — start with core notes
- **Do NOT dump full file contents** — summarize and point
- **Do NOT skip the briefing** — orient yourself even if not asked
"""
    # Consolidate skill
    consolidate = """---
name: consolidate
description: Distill recent claude-mem session observations into the Obsidian vault. Run at session end or on demand to keep vault knowledge current.
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

**Rule**: If it helps a FUTURE session understand the project better → vault. If only about THIS session → claude-mem.

### Step 3: Update Vault Notes

Use `create_vault_file` or `patch_vault_file` to write to the `Claude/` folder. Update existing notes rather than creating new ones.

### Step 4: Verify

Read back modified notes to confirm correctness.

## Anti-Patterns

- **Do NOT duplicate** what's already in claude-mem
- **Do NOT overwrite** existing content — append or update sections
- **Do NOT store temporary state** — "currently debugging X" goes to claude-mem
- **Do NOT create new notes unless truly necessary** — add to existing notes
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


def _write_rest_api_config(vault_path: Path, port: int, api_key: str, dry_run: bool = False) -> None:
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


def _write_mcp_connector_config(vault_path: Path, bearer_token: str, dry_run: bool = False) -> None:
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
        print_success(f"Configured MCP Connector with bearer token")


def _generate_claude_md(vault_name: str, vault_path: Path, dry_run: bool = False) -> None:
    """Generate CLAUDE.md at vault root."""
    content = f"""# {vault_name.title()}

## Memory Architecture (3 Layers)

This project uses a 3-layer memory system. **Never duplicate knowledge across layers.**

| Layer | What | Where | Search |
|-------|------|------|--------|
| 1. claude-mem | Session observations, "how did we fix X?" | SQLite + Chroma (`~/.claude-mem/`) | `/mem-search`, MCP tools |
| 2. Obsidian vault | Project knowledge, user preferences, decisions | `Claude/` folder (this vault) | obsidian-mcp-tools |
| 3. Claude native | Pointer ONLY — never store knowledge here | `memory/MEMORY.md` | — |

### Rules

- **New knowledge → Obsidian vault (Layer 2).** Use `create_vault_file` or `patch_vault_file` to write to `Claude/`.
- **Session observations → claude-mem (Layer 1).** Automatic via hooks.
- **Claude native memory → pointer only.** `memory/MEMORY.md` should only say "Use MCP tools to read/write the vault."
- **If in doubt**, ask: "Is this a session-level observation or project-level knowledge?"

### Semantic Search

**Primary search method.** Use `search_vault_smart` for all vault lookups. It uses the MCP Connector's built-in Transformers.js and re-indexes on every query — always up to date.

Fallback: `search_vault_simple` for substring search when the semantic index is initializing or you need exact matches.

Only use `get_vault_file` directly when you already know the exact file and need its full content.

### Session Lifecycle

- **Start**: Read `Claude/MEMORY.md` for context.
- **End**: Run `/consolidate` to distill claude-mem observations into vault notes.

## User Preferences

- **Language:** Spanish for conversation, English for code
- **Collaboration style:** See `Claude/user.md`
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
                print_warning(f"{claude_md} already contains memory architecture section. Skipping.")
        else:
            claude_md.write_text(content, encoding="utf-8")
            print_success(f"Created {claude_md}")


def _generate_memory_md(vault_path: Path, dry_run: bool = False) -> None:
    """Generate Claude/MEMORY.md (Layer 3 pointer)."""
    content = """# Memory Index

This is a pointer file. Do NOT store knowledge here — use the vault instead.

## How to Access Knowledge

- **Vault notes**: Use `get_vault_file("Claude/user.md")` or `search_vault_smart("query")`
- **Session observations**: Use `/mem-search` or claude-mem MCP tools
- **Never** store full knowledge here — this file is just an index

## Vault Notes

| Note | Purpose |
|------|---------|
| `user.md` | User profile, preferences, communication style |
| `projects.md` | Project catalog and status |
| `insights.md` | Cross-project lessons learned |

## Search

- **Primary**: `search_vault_smart(query)` — MCP Connector Transformers.js, always up to date
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


def run(
    vault_name: str,
    vault_path: str,
    dry_run: bool = False,
    skip_semantic: bool = False,
    non_interactive: bool = False,
) -> dict:
    """Create vault directory structure and configure plugins.

    Returns:
        Dict with generated config for downstream phases.
    """
    vault = Path(vault_path).expanduser().resolve()

    if not re.match(r'^[a-zA-Z0-9_-]+$', vault_name):
        print_error(f"Invalid vault name '{vault_name}'. Use only letters, numbers, hyphens, and underscores.")
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

    # Step 7b: Write Claude Code skills
    print_step("Writing Claude Code skills")
    _write_skills(vault_name, vault, dry_run)

    # Step 8: Open Obsidian to load plugins
    print_step("Opening Obsidian")
    _open_obsidian(vault, dry_run)

    # Return config for Phase 3
    return {
        "vault_path": str(vault),
        "vault_name": vault_name,
        "rest_api_port": rest_port,
        "mcp_http_port": mcp_port,
        "api_key": api_key,
        "bearer_token": bearer_token,
    }