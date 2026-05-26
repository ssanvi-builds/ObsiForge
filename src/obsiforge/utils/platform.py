"""Cross-platform path detection and platform utilities."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
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


def get_obsidian_config_dir() -> Path:
    """Return the Obsidian config directory for the current platform.

    Obsidian stores its vault registry (obsidian.json) and other config here:
    - macOS: ~/Library/Application Support/obsidian/
    - Linux: ~/.config/obsidian/
    - Windows: %APPDATA%/obsidian/
    """
    plat = get_platform()
    if plat == "macos":
        return Path.home() / "Library" / "Application Support" / "obsidian"
    if plat == "linux":
        return Path.home() / ".config" / "obsidian"
    if plat == "windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "obsidian"
    return Path.home() / ".config" / "obsidian"


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

    Checks PATH first, then platform-specific install locations.
    On macOS, checks /Applications.
    On Linux, checks deb/rpm/AppImage/snap/flatpak paths.
    On Windows, checks Program Files.
    """
    # Try PATH first (works for any install method)
    from_path = find_executable("obsidian")
    if from_path:
        return from_path

    # Try obsidian-bin (AUR package name)
    from_path_bin = find_executable("obsidian-bin")
    if from_path_bin:
        return from_path_bin

    plat = get_platform()
    if plat == "macos":
        app_path = Path("/Applications/Obsidian.app")
        if app_path.exists():
            return app_path
    elif plat == "linux":
        for candidate in [
            # deb package (symlink)
            Path("/usr/bin/obsidian"),
            # deb package (actual binary)
            Path("/opt/Obsidian/obsidian"),
            # rpm package (Fedora/openSUSE)
            Path("/usr/lib64/obsidian/obsidian"),
            # Snap
            Path("/snap/bin/obsidian"),
            # User-local bin (symlinks, AppImage wrappers)
            Path.home() / ".local" / "bin" / "obsidian",
            # Common AppImage locations
            Path.home() / "Applications" / "Obsidian.AppImage",
            Path.home() / "Applications" / "obsidian.AppImage",
            Path.home() / "Downloads" / "Obsidian.AppImage",
            # AUR obsidian-bin
            Path("/usr/bin/obsidian-bin"),
        ]:
            if candidate.exists():
                return candidate

        # Flatpak: check if installed but not in PATH
        try:
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and "obsidian" in result.stdout.lower():
                return Path("flatpak:md.obsidian.Obsidian")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    elif plat == "windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", "C:/Program Files")  # noqa: SIM112
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")  # noqa: SIM112
        for candidate in [
            # User install (most common — Electron apps install here)
            Path(local_app) / "Obsidian" / "Obsidian.exe",
            # System-wide install
            Path(program_files) / "Obsidian" / "Obsidian.exe",
            # 32-bit on 64-bit system
            Path(program_files_x86) / "Obsidian" / "Obsidian.exe",
        ]:
            if candidate.exists():
                return candidate

    # Last resort: check if Obsidian is running (cross-platform)
    if plat == "windows":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe"],
                capture_output=True, text=True, timeout=5,
            )
            if "Obsidian.exe" in result.stdout:
                return Path("running (found process, path unknown)")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            result = subprocess.run(
                ["pgrep", "-x", "obsidian"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return Path("running (found process, path unknown)")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return None


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