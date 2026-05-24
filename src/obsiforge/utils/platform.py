"""Cross-platform path detection and platform utilities."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


def get_platform() -> str:
    """Return the current platform: 'macos', 'linux', or 'windows'."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    return system


def get_claude_config_dir() -> Path:
    """Return the Claude Code config directory for the current platform.

    Returns:
        Path to ~/.claude/ on macOS/Linux, %APPDATA%/claude/ on Windows.
    """
    plat = get_platform()
    if plat == "windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "claude"
    return Path.home() / ".claude"


def get_obsidian_vaults_dir() -> Path:
    """Return the default Obsidian vaults directory.

    On macOS: ~/obsidian-vaults/
    On Linux: ~/obsidian-vaults/
    On Windows: %USERPROFILE%/obsidian-vaults/

    Users can override this during setup.
    """
    return Path.home() / "obsidian-vaults"


def find_executable(name: str) -> Path | None:
    """Find an executable on PATH.

    Args:
        name: Executable name (e.g. 'node', 'python3', 'claude').

    Returns:
        Path to the executable, or None if not found.
    """
    result = shutil.which(name)
    return Path(result) if result else None


def get_node_path() -> Path | None:
    """Find the Node.js executable."""
    return find_executable("node")


def get_python_path() -> Path | None:
    """Find the Python 3 executable."""
    return find_executable("python3") or find_executable("python")


def get_uv_path() -> Path | None:
    """Find the uv executable."""
    return find_executable("uv")


def get_claude_path() -> Path | None:
    """Find the Claude Code CLI executable."""
    return find_executable("claude")


def get_git_path() -> Path | None:
    """Find the git executable."""
    return find_executable("git")


def get_obsidian_path() -> Path | None:
    """Find the Obsidian app executable.

    On macOS, checks common install locations.
    On Linux, checks snap/flatpak/AppImage paths.
    On Windows, checks Program Files.
    """
    plat = get_platform()
    if plat == "macos":
        app_path = Path("/Applications/Obsidian.app")
        if app_path.exists():
            return app_path
    elif plat == "linux":
        for candidate in [
            Path.home() / ".local" / "bin" / "obsidian",
            Path("/snap/bin/obsidian"),
            Path("/usr/bin/obsidian"),
        ]:
            if candidate.exists():
                return candidate
    elif plat == "windows":
        for candidate in [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Obsidian" / "Obsidian.exe",
            Path("C:/Program Files/Obsidian/Obsidian.exe"),
        ]:
            if candidate.exists():
                return candidate
    return None


def expand_path(path: str) -> Path:
    """Expand ~ and environment variables in a path string."""
    return Path(os.path.expandvars(os.path.expanduser(path)))


def get_claude_mem_path() -> Path | None:
    """Find the claude-mem MCP server path."""
    default = (
        Path.home()
        / ".claude"
        / "plugins"
        / "marketplaces"
        / "thedotmack"
        / "plugin"
        / "scripts"
        / "mcp-server.cjs"
    )
    if default.exists():
        return default
    return None


def get_brew_path() -> Path | None:
    """Find the Homebrew executable.

    Checks both Apple Silicon (/opt/homebrew) and Intel (/usr/local) prefixes.
    """
    # Apple Silicon path takes priority
    for candidate in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
        path = Path(candidate)
        if path.exists():
            return path
    return find_executable("brew")


def detect_package_manager() -> str | None:
    """Detect the available system package manager.

    Returns:
        One of: 'brew', 'apt', 'dnf', 'pacman', 'winget', 'choco', or None.
    """
    plat = get_platform()

    if plat == "macos":
        return "brew" if get_brew_path() else None

    if plat == "linux":
        for cmd, name in [("apt-get", "apt"), ("dnf", "dnf"), ("pacman", "pacman")]:
            if find_executable(cmd):
                return name
        return None

    if plat == "windows":
        if find_executable("winget"):
            return "winget"
        if find_executable("choco"):
            return "choco"
        return None

    return None