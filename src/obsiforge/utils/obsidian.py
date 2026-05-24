"""Shared Obsidian process and port detection utilities."""

from __future__ import annotations

import re
import socket
import subprocess
from typing import Any

from obsiforge.utils.platform import get_platform


def is_obsidian_running() -> dict[str, Any]:
    """Check if Obsidian is running (cross-platform).

    Returns:
        Dict with 'running' (bool) and 'pids' (list of str).
    """
    plat = get_platform()
    try:
        if plat == "windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe"],
                capture_output=True, text=True, timeout=5,
            )
            if "Obsidian.exe" in result.stdout:
                return {"running": True, "pids": []}
        else:
            flag = "-x" if plat == "macos" else "-f"
            name = "Obsidian" if plat == "macos" else "obsidian"
            result = subprocess.run(
                ["pgrep", flag, name],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return {"running": True, "pids": result.stdout.strip().split("\n")}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return {"running": False, "pids": []}


def check_port_in_use(port: int) -> bool:
    """Check if a specific TCP port is in use on localhost.

    Returns:
        True if port is in use (connection succeeds), False otherwise.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result == 0
    except OSError:
        return False


def find_obsidian_listening_ports() -> list[int]:
    """Find ports that the Obsidian process is listening on.

    Uses platform-specific commands (lsof on macOS, ss on Linux,
    netstat on Windows) to discover Obsidian's listening ports.

    Returns:
        Sorted list of unique port numbers.
    """
    plat = get_platform()
    ports: list[int] = []
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
                    ports.append(int(match.group(1)))
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
                    ports.append(int(match.group(1)))
        elif plat == "windows":
            pid_result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            obsidian_pids: set[str] = set()
            for line in pid_result.stdout.splitlines():
                if "Obsidian" in line:
                    parts = line.strip('"').split('","')
                    if len(parts) >= 2:
                        obsidian_pids.add(parts[1])
            if obsidian_pids:
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True, timeout=10,
                )
                for line in result.stdout.splitlines():
                    if "LISTENING" not in line:
                        continue
                    pid = line.strip().split()[-1]
                    if pid not in obsidian_pids:
                        continue
                    match = re.search(r"(?:127\.0\.0\.1|0\.0\.0\.0):(\d+)", line)
                    if match:
                        ports.append(int(match.group(1)))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return sorted(set(ports))