"""Phase 4: Verify all components are working."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.table import Table

from obsiforge.utils.llm_providers import is_provider_configured, load_claude_mem_settings
from obsiforge.utils.obsidian import check_port_in_use
from obsiforge.utils.platform import get_claude_config_dir
from obsiforge.utils.ports import CLAUDE_MEM_WORKER_PORT
from obsiforge.utils.prompt import print_step, print_success, print_warning

console = Console()


def _get_claude_mem_worker_port() -> int:
    """Read actual worker port from claude-mem settings, with fallback."""
    settings = load_claude_mem_settings()
    return int(settings.get("CLAUDE_MEM_WORKER_PORT", CLAUDE_MEM_WORKER_PORT))


def _check_claude_mem_worker() -> dict[str, Any]:
    """Check if claude-mem worker is running."""
    port = _get_claude_mem_worker_port()
    try:
        resp = httpx.get(f"http://localhost:{port}/health", timeout=5)
        if resp.status_code == 200:
            return {"status": "running", "details": "worker healthy"}
    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    return {
        "status": "stopped",
        "details": f"worker not responding on port {port}",
    }


def _check_mcp_http(port: int) -> dict[str, Any]:
    """Check if MCP Connector HTTP server is responding on a port."""
    if check_port_in_use(port):
        return {"status": "running", "details": f"port {port} is open"}
    return {
        "status": "stopped",
        "details": f"port {port} is not responding (Obsidian not running?)",
    }


def _check_rest_api(port: int, api_key: str) -> dict[str, Any]:
    """Check if Local REST API is responding."""
    try:
        resp = httpx.get(
            f"https://localhost:{port}/",
            headers={"Authorization": f"Bearer {api_key}"},
            verify=False,
            timeout=5,
        )
        if resp.status_code in (200, 401):
            return {"status": "running", "details": f"REST API on port {port}"}
    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    return {"status": "stopped", "details": f"REST API not responding on port {port}"}


def _check_vault_files(vault_path: str) -> dict[str, Any]:
    """Check if required vault files exist and semantic index coverage."""
    vault = Path(vault_path)
    required = [
        vault / "CLAUDE.md",
        vault / "Claude" / "MEMORY.md",
        vault / ".mcp.json",
        vault / ".claude" / "settings.local.json",
        vault / ".obsidian" / "community-plugins.json",
        vault / ".obsidian" / "workspace.json",
    ]

    missing = [str(f.relative_to(vault)) for f in required if not f.exists()]
    if missing:
        return {"status": "partial", "details": f"missing: {', '.join(missing)}"}

    md_files = list(vault.rglob("*.md"))
    md_files = [f for f in md_files if ".obsidian" not in str(f) and ".claude" not in str(f)]
    total_notes = len(md_files)

    return {"status": "ok", "details": f"all files present ({total_notes} notes)"}


def _check_settings_json() -> dict[str, Any]:
    """Check if global settings.json has required MCP entries."""
    config_dir = get_claude_config_dir()
    settings_path = config_dir / "settings.json"

    if not settings_path.exists():
        return {"status": "missing", "details": f"{settings_path} not found"}

    try:
        settings = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return {"status": "error", "details": "invalid JSON"}

    servers = settings.get("mcpServers", {})
    has_mem = "claude-mem" in servers

    if has_mem:
        return {"status": "ok", "details": "claude-mem configured"}
    return {"status": "partial", "details": "claude-mem not in mcpServers"}


def _check_hooks() -> dict[str, Any]:
    """Check if required hooks are configured."""
    config_dir = get_claude_config_dir()
    settings_path = config_dir / "settings.json"

    if not settings_path.exists():
        return {"status": "missing", "details": "settings.json not found"}

    try:
        settings = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return {"status": "error", "details": "invalid JSON"}

    hooks = settings.get("hooks", {})
    has_session_start = any(
        any(h.get("command", "").startswith("npx claude-mem") for h in group.get("hooks", []))
        for group in hooks.get("SessionStart", [])
    )
    has_consolidate = any(
        any("consolidate" in h.get("command", "") for h in group.get("hooks", []))
        for group in hooks.get("Stop", [])
    )

    if has_session_start and has_consolidate:
        return {"status": "ok", "details": "SessionStart + consolidate Stop hooks configured"}
    missing = []
    if not has_session_start:
        missing.append("SessionStart")
    if not has_consolidate:
        missing.append("Stop consolidate")
    return {"status": "partial", "details": f"missing: {', '.join(missing)}"}


def _check_llm_provider() -> dict[str, Any]:
    """Check if claude-mem has an LLM provider configured."""
    result = is_provider_configured()
    if result["configured"]:
        return {"status": "ok", "details": result["details"]}
    return {"status": "partial", "details": result["details"]}


def run(
    vault_name: str,
    vault_path: str,
    dry_run: bool = False,
    non_interactive: bool = False,
) -> dict[str, Any]:
    """Check that all MCP servers respond and vault is accessible.

    Returns:
        Dict with verification results.
    """
    if dry_run:
        print_step("Would verify all components")
        return {"verified": False}

    from obsiforge.utils.state import load_state

    state = load_state()
    vault_state = state.get("vaults", {}).get(vault_name, {})
    rest_port = vault_state.get("rest_api_port")
    mcp_port = vault_state.get("mcp_http_port")
    api_key = vault_state.get("api_key", "")

    if not rest_port or not mcp_port:
        return {
            "verified": False,
            "checks": {},
            "error": "Missing port config in state. Run 'obsiforge init' first.",
        }

    # Wait for Obsidian plugins to start (they need a few seconds to load)
    import time

    console.print("[dim]Waiting for Obsidian plugins to initialize...[/dim]")
    for i in range(6):
        time.sleep(3)
        if _check_mcp_http(mcp_port)["status"] == "running":
            break
        if i < 5:
            console.print(f"[dim]  Still waiting... ({i+1}/6)[/dim]")

    checks = {
        "claude-mem worker": _check_claude_mem_worker(),
        "LLM provider": _check_llm_provider(),
        "MCP Connector": _check_mcp_http(mcp_port),
        "Local REST API": (
            _check_rest_api(rest_port, api_key)
            if api_key
            else {"status": "skipped", "details": "no API key"}
        ),
        "vault files": _check_vault_files(vault_path),
        "global settings": _check_settings_json(),
        "hooks": _check_hooks(),
    }

    # Display results
    table = Table(title="Verification", show_lines=True)
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    status_style = {
        "ok": "[green]OK[/green]",
        "running": "[green]RUNNING[/green]",
        "partial": "[yellow]PARTIAL[/yellow]",
        "stopped": "[yellow]STOPPED[/yellow]",
        "missing": "[red]MISSING[/red]",
        "error": "[red bold]ERROR[/red bold]",
        "skipped": "[dim]SKIPPED[/dim]",
    }

    for component, info in checks.items():
        style = status_style.get(info["status"], info["status"])
        table.add_row(component, style, info.get("details", ""))

    console.print(table)

    # Summary
    all_ok = all(info["status"] in ("ok", "running") for info in checks.values())
    if all_ok:
        print_success("All components verified!")
    else:
        issues = [k for k, v in checks.items() if v["status"] not in ("ok", "running", "skipped")]
        if issues:
            print_warning(f"Some components need attention: {', '.join(issues)}")
            console.print(
                "\n[bold]Next steps to complete setup:[/bold]\n"
                "  1. Open Obsidian with your vault\n"
                "  2. Go to [bold]Settings → Community plugins[/bold]\n"
                "  3. Click [bold]Turn on community plugins[/bold]"
                " (trust dialog)\n"
                "  4. Enable each plugin toggle "
                "([bold]MCP Tools[/bold], [bold]Local REST API[/bold])\n"
                "  5. Restart Obsidian or reload ([bold]Cmd+R[/bold])\n"
            )
            print_warning("Run 'obsiforge doctor' for detailed diagnostics.")

    return {"verified": all_ok, "checks": checks}


def get_status() -> dict[str, dict[str, str]]:
    """Return status of all components for the status command.

    Returns:
        Dict mapping component name to status dict.
    """
    # Quick checks without needing vault state
    mem_check = _check_claude_mem_worker()
    settings_check = _check_settings_json()
    hooks_check = _check_hooks()

    return {
        "claude-mem": mem_check,
        "LLM provider": _check_llm_provider(),
        "obsidian-mcp-tools": {
            "status": "ok" if settings_check["status"] == "ok" else "unknown",
            "details": "check with 'obsiforge doctor'",
        },
        "hooks": hooks_check,
        "global settings": settings_check,
    }