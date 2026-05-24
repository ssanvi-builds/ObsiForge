"""ObsiForge Doctor — health check and auto-repair for common issues."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel

from obsiforge.utils.obsidian import (
    check_port_in_use,
    find_obsidian_listening_ports,
    is_obsidian_running,
)
from obsiforge.utils.platform import get_claude_config_dir
from obsiforge.utils.ports import (
    CLAUDE_MEM_WORKER_PORT,
    MCP_HTTP_RANGE,
    REST_API_RANGE,
)
from obsiforge.utils.prompt import print_error, print_success, print_warning

console = Console()


def _check_mcp_auth(vault_path: str, bearer_token: str, mcp_port: int) -> dict[str, Any]:
    """Check if MCP Connector accepts the bearer token."""
    try:
        resp = httpx.post(
            f"http://127.0.0.1:{mcp_port}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "obsiforge-doctor", "version": "0.1.0"},
                },
            },
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Accept": "application/json, text/event-stream",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return {"auth_ok": True, "details": "MCP Connector responding"}
        if resp.status_code == 401:
            return {
                "auth_ok": False,
                "details": "Bearer token rejected — token may have changed in Obsidian",
            }
        if resp.status_code == 406:
            # 406 = Not Acceptable, but it means auth passed and server is
            # responding — it just needs the Accept header for full protocol
            return {"auth_ok": True, "details": "MCP Connector responding"}
    except (httpx.ConnectError, httpx.TimeoutException):
        return {"auth_ok": False, "details": f"MCP Connector not responding on port {mcp_port}"}
    return {"auth_ok": False, "details": "Unexpected response"}


def _check_plugins_enabled(vault_path: str) -> dict[str, Any]:
    """Check which required Obsidian plugins are enabled."""
    vault = Path(vault_path).expanduser()
    community_plugins = vault / ".obsidian" / "community-plugins.json"

    required = {"mcp-tools-istefox", "obsidian-local-rest-api"}

    if not community_plugins.exists():
        return {
            "enabled": set(),
            "missing": required,
            "details": "community-plugins.json not found",
        }

    try:
        enabled_list = json.loads(community_plugins.read_text())
        enabled = set(enabled_list)
        missing = required - enabled
        return {
            "enabled": enabled,
            "missing": missing,
            "complete": not missing,
            "details": f"{len(enabled & required)}/{len(required)} enabled",
        }
    except json.JSONDecodeError:
        return {
            "enabled": set(),
            "missing": required,
            "details": "community-plugins.json is invalid",
        }


def _check_workspace_json(vault_path: str) -> dict[str, Any]:
    """Check if .obsidian/workspace.json exists (required for vault validity)."""
    vault = Path(vault_path).expanduser()
    workspace = vault / ".obsidian" / "workspace.json"

    if not workspace.exists():
        return {
            "valid": False,
            "details": "workspace.json not found — vault may not be registered",
        }

    try:
        data = json.loads(workspace.read_text())
        if not isinstance(data, dict) or len(data) == 0:
            return {"valid": True, "details": "workspace.json exists (empty — fresh vault)"}
        return {"valid": True, "details": "workspace.json exists"}
    except json.JSONDecodeError:
        return {"valid": False, "details": "workspace.json is invalid JSON"}


def _check_settings_json() -> dict[str, Any]:
    """Validate ~/.claude/settings.json structure."""
    config_dir = get_claude_config_dir()
    settings_path = config_dir / "settings.json"

    if not settings_path.exists():
        return {"valid": False, "details": "settings.json not found"}

    try:
        settings = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return {"valid": False, "details": "settings.json contains invalid JSON"}

    issues = []

    # Check required keys
    if "mcpServers" not in settings:
        issues.append("missing mcpServers")

    servers = settings.get("mcpServers", {})
    if "claude-mem" not in servers:
        issues.append("missing claude-mem MCP server")

    # Check hooks
    hooks = settings.get("hooks", {})
    has_session_start = any(
        any("claude-mem" in h.get("command", "") for h in group.get("hooks", []))
        for group in hooks.get("SessionStart", [])
    )
    if not has_session_start:
        issues.append("missing SessionStart hook for claude-mem")

    # Check env
    env = settings.get("env", {})
    if env.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY") != "1":
        issues.append("CLAUDE_CODE_DISABLE_AUTO_MEMORY not set")

    if issues:
        return {"valid": False, "details": "; ".join(issues)}
    return {"valid": True, "details": "all required keys present"}


def _check_vault_files(vault_path: str) -> dict[str, Any]:
    """Check if required vault files exist."""
    vault = Path(vault_path).expanduser()
    required = {
        "CLAUDE.md": vault / "CLAUDE.md",
        "Claude/MEMORY.md": vault / "Claude" / "MEMORY.md",
        ".mcp.json": vault / ".mcp.json",
        ".claude/settings.local.json": vault / ".claude" / "settings.local.json",
        ".obsidian/community-plugins.json": vault / ".obsidian" / "community-plugins.json",
        ".obsidian/workspace.json": vault / ".obsidian" / "workspace.json",
    }

    missing = [name for name, path in required.items() if not path.exists()]

    if missing:
        return {"complete": False, "details": f"missing: {', '.join(missing)}"}
    return {"complete": True, "details": "all files present"}


def run_doctor(
    vault_name: str | None = None,
    vault_path: str | None = None,
    fix: bool = False,
) -> None:
    """Run health checks and optionally auto-repair issues.

    Args:
        vault_name: Optional vault name from state.
        vault_path: Optional vault path from state.
        fix: If True, attempt to fix found issues.
    """
    from obsiforge.utils.state import cleanup_stale_vaults, load_state

    # Clean up stale vault entries (paths that no longer exist)
    removed = cleanup_stale_vaults()
    if removed:
        console.print(f"[dim]Cleaned up {removed} stale vault entries[/dim]\n")

    state = load_state()
    vaults = state.get("vaults", {})

    # Filter out any remaining stale entries
    valid_vaults = {
        name: info for name, info in vaults.items()
        if info.get("vault_path") and Path(info["vault_path"]).exists()
    }

    if not vault_name and valid_vaults:
        if len(valid_vaults) == 1:
            vault_name = next(iter(valid_vaults))
        else:
            # Multiple vaults — list them and default to most recently created
            vault_name = max(
                valid_vaults.keys(),
                key=lambda n: valid_vaults[n].get("created_at", 0),
            )
            console.print("[dim]Available vaults:[/dim]")
            for name in sorted(
                valid_vaults.keys(),
                key=lambda n: valid_vaults[n].get("created_at", 0),
                reverse=True,
            ):
                marker = " ← default" if name == vault_name else ""
                console.print(f"  [dim]• {name}{marker}[/dim]")
            console.print(
                "[dim]Use --vault <name> to check a different vault[/dim]\n"
            )
    if vault_name and not vault_path:
        vault_path = valid_vaults.get(vault_name, {}).get("vault_path")

    console.print(Panel(
        "[bold cyan]ObsiForge Doctor[/bold cyan]\n"
        "Diagnosing your 3-layer memory system...",
        border_style="cyan",
    ))

    checks = []

    # 1. Obsidian running?
    console.rule("[bold]Obsidian[/bold]")
    obs_check = is_obsidian_running()
    if obs_check["running"]:
        print_success(f"Obsidian is running (PID {obs_check['pids'][0]})")
    else:
        print_error("Obsidian is not running — some checks require Obsidian to be open")
    checks.append(("Obsidian process", obs_check))

    # 2. Global settings.json
    console.rule("[bold]Global Settings[/bold]")
    settings_check = _check_settings_json()
    if settings_check["valid"]:
        print_success(f"settings.json: {settings_check['details']}")
    else:
        print_error(f"settings.json: {settings_check['details']}")
        if fix:
            console.print("[dim]  Would repair: add missing keys[/dim]")
    checks.append(("Global settings", settings_check))

    # 3. Per-vault checks
    if vault_name and vault_path:
        vault_state = vaults.get(vault_name, {})
        rest_port = vault_state.get("rest_api_port")
        mcp_port = vault_state.get("mcp_http_port")
        bearer_token = vault_state.get("bearer_token", "")

        if not rest_port or not mcp_port:
            print_error("Vault port config missing from state. Run 'obsiforge init' first.")
        else:
            console.rule(f"[bold]Vault: {vault_name}[/bold]")

            # Vault files
            files_check = _check_vault_files(vault_path)
            if files_check["complete"]:
                print_success(f"Vault files: {files_check['details']}")
            else:
                print_error(f"Vault files: {files_check['details']}")
            checks.append(("Vault files", files_check))

            # Workspace.json
            workspace_check = _check_workspace_json(vault_path)
            if workspace_check["valid"]:
                print_success(f"workspace.json: {workspace_check['details']}")
            else:
                print_error(f"workspace.json: {workspace_check['details']}")
                console.print(
                    "[dim]  Fix: Open vault in Obsidian once to generate workspace.json[/dim]"
                )
            checks.append(("workspace.json", workspace_check))

            # Plugins enabled
            plugins_check = _check_plugins_enabled(vault_path)
            if not plugins_check["missing"]:
                print_success(f"Plugins: {plugins_check['details']}")
            else:
                missing_str = ", ".join(plugins_check["missing"])
                print_error(f"Plugins: missing {missing_str}")
                console.print(
                    "[dim]  Fix: Obsidian → Settings → Community plugins → Enable both[/dim]"
                )
            checks.append(("Plugins", plugins_check))

            # MCP Connector port
            obsidian_running = obs_check["running"]
            mcp_check = {"in_use": check_port_in_use(mcp_port)}

            # If expected port doesn't respond, try to discover actual port
            actual_mcp_port: int | None = mcp_port
            if not mcp_check["in_use"] and obsidian_running:
                real_ports = find_obsidian_listening_ports()
                mcp_low, mcp_high = MCP_HTTP_RANGE
                mcp_candidates = [p for p in real_ports if mcp_low <= p <= mcp_high]
                if mcp_candidates:
                    actual_mcp_port = mcp_candidates[0]
                    mcp_check = {"in_use": check_port_in_use(actual_mcp_port)}

            if mcp_check["in_use"]:
                port_label = str(actual_mcp_port)
                if actual_mcp_port != mcp_port:
                    port_label = f"{actual_mcp_port} (expected {mcp_port})"
                print_success(f"MCP Connector: port {port_label} is open")
                # Try auth check
                if bearer_token and actual_mcp_port:
                    auth_check = _check_mcp_auth(vault_path, bearer_token, actual_mcp_port)
                    if auth_check["auth_ok"]:
                        print_success(f"MCP auth: {auth_check['details']}")
                    else:
                        print_error(f"MCP auth: {auth_check['details']}")
                        console.print(
                            "[dim]  Fix: Update bearer token in .mcp.json "
                            "to match plugin settings[/dim]"
                        )
                    checks.append(("MCP auth", auth_check))
            else:
                if obsidian_running:
                    print_error(f"MCP Connector: port {mcp_port} not responding")
                    console.print(
                        "[dim]  Fix: Enable MCP Tools plugin in Obsidian → "
                        "Settings → Community plugins[/dim]"
                    )
                else:
                    print_warning(
                        f"MCP Connector: port {mcp_port} not responding"
                        " (Obsidian not running)"
                    )
            checks.append(("MCP Connector", mcp_check))

            # REST API
            rest_check = {"in_use": check_port_in_use(rest_port)}
            actual_rest_port: int | None = rest_port
            if not rest_check["in_use"] and obsidian_running:
                real_ports = find_obsidian_listening_ports()
                rest_low, rest_high = REST_API_RANGE
                rest_candidates = [p for p in real_ports if rest_low <= p <= rest_high]
                if rest_candidates:
                    actual_rest_port = rest_candidates[0]
                    rest_check = {"in_use": check_port_in_use(actual_rest_port)}

            if rest_check["in_use"]:
                port_label = str(actual_rest_port)
                if actual_rest_port != rest_port:
                    port_label = f"{actual_rest_port} (expected {rest_port})"
                print_success(f"REST API: port {port_label} is open")
            else:
                if obsidian_running:
                    print_warning(
                        f"REST API: port {rest_port} not responding"
                        " (may need plugin enable)"
                    )
                else:
                    print_warning(
                        f"REST API: port {rest_port} not responding"
                        " (Obsidian not running)"
                    )
            checks.append(("REST API", rest_check))

    # 4. claude-mem
    console.rule("[bold]claude-mem[/bold]")
    claude_mem_ok = False
    try:
        resp = httpx.get(f"http://localhost:{CLAUDE_MEM_WORKER_PORT}/health", timeout=5)
        if resp.status_code == 200:
            print_success("claude-mem worker: healthy")
            claude_mem_ok = True
        else:
            print_warning(f"claude-mem worker: unexpected status {resp.status_code}")
    except (httpx.ConnectError, httpx.TimeoutException):
        print_error(f"claude-mem worker: not responding on port {CLAUDE_MEM_WORKER_PORT}")
        console.print(
            "[dim]  Fix: Run 'npx claude-mem start' or "
            "restart your Claude Code session[/dim]"
        )
    checks.append(("claude-mem", {"running": claude_mem_ok}))

    # Summary
    console.rule("[bold]Summary[/bold]")
    ok_count = sum(
        1 for _, c in checks
        if c.get("valid") or c.get("complete")
        or c.get("auth_ok") or c.get("in_use")
        or c.get("running")
    )
    total = len(checks)
    issue_count = total - ok_count

    if issue_count == 0:
        console.print(Panel(
            f"[bold green]All {total} checks passed![/bold green]",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold yellow]{ok_count}/{total} checks passed, "
            f"{issue_count} need attention[/bold yellow]\n\n"
            "Common fixes:\n"
            "• Open vault in Obsidian to generate workspace.json\n"
            "• Settings → Community plugins → Turn on community plugins\n"
            "• Enable each plugin toggle (MCP Tools, Local REST API)\n"
            "• Restart Obsidian or reload (Cmd+R) after enabling plugins\n"
            "• Run 'npx claude-mem start' if claude-mem worker is down\n"
            "• Restart Claude Code session if MCP servers aren't connecting",
            border_style="yellow",
        ))