"""Phase 3: Configure MCP servers (per-vault + global)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from obsiforge.utils.prompt import print_dry_run, print_step, print_success, print_warning

console = Console()


def _write_mcp_json(
    vault_path: str,
    vault_name: str,
    mcp_http_port: int,
    bearer_token: str,
    dry_run: bool = False,
) -> None:
    """Create .mcp.json at vault root with streamable-http format."""
    vault = Path(vault_path)
    mcp_file = vault / ".mcp.json"

    # Use vault-specific server name so multiple vaults don't collide
    server_name = f"obsidian-mcp-tools-{vault_name}"

    mcp_config: dict[str, Any] = {
        "mcpServers": {
            server_name: {
                "type": "streamable-http",
                "url": f"http://127.0.0.1:{mcp_http_port}/mcp",
                "headers": {
                    "Authorization": f"Bearer {bearer_token}",
                },
            },
        }
    }

    if dry_run:
        print_dry_run(f"Would write {mcp_file}")
        from obsiforge.utils.settings_merge import _mask_sensitive
        masked = {
            "mcpServers": {
                server_name: {
                    "type": mcp_config["mcpServers"][server_name]["type"],
                    "url": mcp_config["mcpServers"][server_name]["url"],
                    "headers": {
                        "Authorization": f"Bearer {_mask_sensitive(bearer_token)}",
                    },
                },
            }
        }
        console.print(json.dumps(masked, indent=2))
    else:
        # Backup existing if present
        if mcp_file.exists():
            backup = mcp_file.with_suffix(".json.bak")
            mcp_file.rename(backup)
            print_warning(f"Backed up existing {mcp_file} to {backup}")

        mcp_file.write_text(json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
        print_success(f"Created {mcp_file}")


def _write_settings_local(
    vault_path: str,
    vault_name: str = "",
    dry_run: bool = False,
) -> None:
    """Create .claude/settings.local.json with enabledMcpjsonServers."""
    vault = Path(vault_path)
    settings_dir = vault / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file = settings_dir / "settings.local.json"

    # Use vault-specific server name to match .mcp.json
    server_name = f"obsidian-mcp-tools-{vault_name}" if vault_name else "obsidian-mcp-tools"
    tool_prefix = f"mcp__{server_name}__"

    settings = {
        "permissions": {
            "allow": [
                # Read operations
                f"{tool_prefix}get_vault_file",
                f"{tool_prefix}get_server_info",
                f"{tool_prefix}list_vault_files",
                # Write operations
                f"{tool_prefix}create_vault_file",
                f"{tool_prefix}patch_vault_file",
                f"{tool_prefix}append_to_vault_file",
                f"{tool_prefix}update_active_file",
                # Search operations
                f"{tool_prefix}search_vault_simple",
                f"{tool_prefix}search_vault_smart",
                # Link & tag operations
                f"{tool_prefix}get_backlinks",
                f"{tool_prefix}get_outgoing_links",
                f"{tool_prefix}get_files_by_tag",
                f"{tool_prefix}list_tags",
                # claude-mem
                "mcp__plugin_claude-mem_mcp-search__search",
                "mcp__plugin_claude-mem_mcp-search__timeline",
                "mcp__plugin_claude-mem_mcp-search__get_observations",
            ]
        },
        "enabledMcpjsonServers": [
            server_name,
        ],
    }

    if dry_run:
        print_dry_run(f"Would write {settings_file}")
    else:
        settings_file.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        print_success(f"Created {settings_file}")


def run(
    vault_name: str,
    vault_path: str,
    dry_run: bool = False,
    non_interactive: bool = False,
    mcp_http_port: int | None = None,
    bearer_token: str | None = None,
    api_key: str | None = None,
    skip_semantic: bool = False,
) -> dict[str, Any]:
    """Create .mcp.json and merge into global settings.

    Credentials can be passed directly (from Phase 2 results) or read
    from the state file. Direct params take priority.

    Returns:
        Dict with MCP configuration details.
    """
    # Prefer explicit params, then fall back to state file
    if not bearer_token or not api_key or not mcp_http_port:
        from obsiforge.utils.state import load_state

        state = load_state()
        vault_state = state.get("vaults", {}).get(vault_name, {})

        mcp_http_port = mcp_http_port or vault_state.get("mcp_http_port")
        bearer_token = bearer_token or vault_state.get("bearer_token")
        api_key = api_key or vault_state.get("api_key")

    if not bearer_token or not api_key:
        console.print(
            "[bold red]Error:[/bold red] Vault state is missing bearer_token or api_key. "
            "Run [bold]obsiforge init[/bold] first to generate credentials."
        )
        raise SystemExit(1)

    # Step 1: Create .mcp.json
    print_step("Creating .mcp.json")
    _write_mcp_json(
        vault_path=vault_path,
        vault_name=vault_name,
        mcp_http_port=mcp_http_port,
        bearer_token=bearer_token,
        dry_run=dry_run,
    )

    # Step 2: Create .claude/settings.local.json
    print_step("Creating .claude/settings.local.json")
    _write_settings_local(vault_path, vault_name=vault_name, dry_run=dry_run)

    return {
        "mcp_configured": True,
        "mcp_http_port": mcp_http_port,
    }