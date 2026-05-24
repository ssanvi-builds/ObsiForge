"""Port allocation and conflict detection utilities."""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path

# Default port ranges for ObsiForge components
REST_API_BASE = 27124  # Local REST API ports start here
MCP_HTTP_BASE = 27200  # MCP Connector HTTP ports start here
CLAUDE_MEM_WORKER_BASE = 37700  # claude-mem worker ports start here


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is available for binding.

    Args:
        port: Port number to check.
        host: Host to check on (default localhost).

    Returns:
        True if the port is available, False if in use.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0  # Connection refused = available
    except OSError:
        return True


def _get_state_reserved_ports() -> set[int]:
    """Get ports reserved by other vaults in the state file."""
    state_path = Path.home() / ".claude" / "obsiforge-state.json"
    if not state_path.exists():
        return set()

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()

    ports: set[int] = set()
    for vault_config in state.get("vaults", {}).values():
        for key in ("rest_api_port", "mcp_http_port"):
            port = vault_config.get(key)
            if isinstance(port, int):
                ports.add(port)
    return ports


def find_available_port(
    base: int,
    host: str = "127.0.0.1",
    max_tries: int = 100,
    exclude: set[int] | None = None,
) -> int:
    """Find the next available port starting from base.

    Args:
        base: Starting port number.
        host: Host to check on.
        max_tries: Maximum number of ports to check.
        exclude: Optional set of ports to skip (reserved by other vaults).

    Returns:
        First available port number.

    Raises:
        RuntimeError: If no port is available in the range.
    """
    excluded = exclude or set()
    for offset in range(max_tries):
        port = base + offset
        if port in excluded:
            continue
        if is_port_available(port, host):
            return port
    msg = f"No available port found in range {base}-{base + max_tries - 1}"
    raise RuntimeError(msg)


def get_used_ports() -> dict[int, str]:
    """Get a map of used ports to their processes.

    Uses lsof on macOS/Linux. Falls back to netstat on other platforms.

    Returns:
        Dict mapping port number to process name.
    """
    ports: dict[int, str] = {}
    try:
        result = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines()[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 9:
                try:
                    addr = parts[8]  # e.g. "*:27124" or "127.0.0.1:27201"
                    port = int(addr.rsplit(":", 1)[-1])
                    ports[port] = parts[0]  # process name
                except (ValueError, IndexError):
                    continue
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ports


def allocate_ports(vault_name: str) -> dict[str, int]:
    """Allocate ports for a new vault.

    Allocates one REST API port and one MCP HTTP port.
    Skips ports already in use by other vaults (from state file) or services (from lsof).

    Args:
        vault_name: Name of the vault (used for logging).

    Returns:
        Dict with 'rest_api' and 'mcp_http' port numbers.
    """
    # Combine ports reserved in state file and ports currently in use
    state_reserved = _get_state_reserved_ports()

    rest_port = find_available_port(REST_API_BASE, exclude=state_reserved)

    # Make sure MCP port doesn't collide with the REST port
    mcp_port = find_available_port(MCP_HTTP_BASE, exclude=state_reserved | {rest_port})

    return {"rest_api": rest_port, "mcp_http": mcp_port}