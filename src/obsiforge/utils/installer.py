"""Platform-aware prerequisite installer for ObsiForge.

Installs missing tools automatically using the best available method
for the current platform. Supports macOS (Homebrew or standalone),
Linux (apt/dnf/pacman + fnm), and Windows (winget + fnm).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable

from rich.console import Console

from obsiforge.utils.platform import (
    detect_package_manager,
    find_executable,
    get_brew_path,
    get_platform,
)

console = Console()


def _run_cmd(cmd: list[str], description: str, timeout: int = 300) -> bool:
    """Run a shell command and report success/failure.

    Returns True if the command succeeded (exit code 0).
    """
    console.print(f"  [dim]Running: {' '.join(cmd)}[/dim]")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            console.print(f"  [green]✓[/green] {description}")
            return True
        console.print(f"  [red]✗[/red] {description} failed:")
        if result.stderr:
            for line in result.stderr.strip().split("\n")[:3]:
                console.print(f"    [dim]{line}[/dim]")
        return False
    except subprocess.TimeoutExpired:
        console.print(f"  [red]✗[/red] {description} timed out ({timeout}s)")
        return False
    except FileNotFoundError:
        console.print(f"  [red]✗[/red] Command not found: {cmd[0]}")
        return False


def _confirm_install(tool: str, non_interactive: bool) -> bool:
    """Ask user to confirm installation.

    Returns True if user confirms or non_interactive is set.
    """
    if non_interactive:
        return True
    from obsiforge.utils.prompt import confirm

    return confirm(f"  Install {tool}?", default=True)


def _check_tool(tool_cmd: str) -> bool:
    """Check if a tool is available on PATH."""
    return find_executable(tool_cmd) is not None


# ─── Node.js ───────────────────────────────────────────────────────


def install_fnm(non_interactive: bool = False, dry_run: bool = False) -> bool:
    """Install fnm (Fast Node Manager)."""
    if _check_tool("fnm"):
        return True

    plat = get_platform()
    if dry_run:
        console.print("  [dim]Would install fnm (Fast Node Manager)[/dim]")
        return True

    if not _confirm_install("fnm (Fast Node Manager)", non_interactive):
        return False

    if plat == "macos":
        brew = get_brew_path()
        if brew:
            return _run_cmd([str(brew), "install", "fnm"], "fnm via Homebrew")
        # Standalone install via curl
        return _run_cmd(
            ["bash", "-c", "curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell"],
            "fnm via curl",
        )

    if plat == "linux":
        return _run_cmd(
            ["bash", "-c", "curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell"],
            "fnm via curl",
        )

    if plat == "windows":
        if find_executable("winget"):
            return _run_cmd(["winget", "install", "Schniz.fnm"], "fnm via winget")
        if find_executable("choco"):
            return _run_cmd(["choco", "install", "fnm", "-y"], "fnm via Chocolatey")

    console.print("  [yellow]⚠[/yellow] Cannot install fnm on this platform automatically.")
    console.print("  Install manually: https://github.com/Schniz/fnm#installation")
    return False


def install_node(non_interactive: bool = False, dry_run: bool = False) -> bool:
    """Install Node.js via fnm or system package manager.

    Strategy: fnm first (for version control), then Homebrew on macOS.
    """
    if _check_tool("node"):
        return True

    plat = get_platform()
    if dry_run:
        console.print("  [dim]Would install Node.js[/dim]")
        return True

    if not _confirm_install("Node.js", non_interactive):
        return False

    # Try fnm first (cross-platform, version-managed)
    if not _check_tool("fnm") and not install_fnm(
        non_interactive=non_interactive, dry_run=dry_run
    ):
        # fnm install failed, try direct install
            if plat == "macos" and get_brew_path():
                return _run_cmd([str(get_brew_path()), "install", "node"], "Node.js via Homebrew")
            if plat == "linux":
                pkg_mgr = detect_package_manager()
                if pkg_mgr == "apt":
                    return _run_cmd(
                        ["sudo", "apt-get", "install", "-y", "nodejs"],
                        "Node.js via apt",
                    )
            console.print("  [yellow]⚠[/yellow] Could not install Node.js automatically.")
            console.print("  Install manually: https://nodejs.org/")
            return False

    # fnm is available, install Node.js LTS via fnm
    fnm_path = find_executable("fnm")
    if not fnm_path:
        console.print("  [red]✗[/red] fnm not found after installation")
        return False

    # Install and use Node.js LTS
    env = dict(os.environ)
    # Ensure fnm is on PATH for the subprocess
    env["PATH"] = str(fnm_path.parent) + ":" + env.get("PATH", "")

    success = _run_cmd(
        [str(fnm_path), "install", "--lts"],
        "Node.js LTS via fnm",
        timeout=120,
    )
    if success:
        _run_cmd([str(fnm_path), "use", "--lts"], "Setting Node.js LTS as default")

    return success


# ─── Obsidian ──────────────────────────────────────────────────────


def install_obsidian(non_interactive: bool = False, dry_run: bool = False) -> bool:
    """Install Obsidian app.

    macOS: Homebrew cask or direct download
    Linux: snap or direct download
    Windows: winget
    """
    from obsiforge.utils.platform import get_obsidian_path

    if get_obsidian_path():
        return True

    plat = get_platform()
    if dry_run:
        console.print("  [dim]Would install Obsidian[/dim]")
        return True

    if not _confirm_install("Obsidian", non_interactive):
        return False

    if plat == "macos":
        brew = get_brew_path()
        if brew:
            return _run_cmd([str(brew), "install", "--cask", "obsidian"], "Obsidian via Homebrew")
        console.print("  [yellow]⚠[/yellow] Homebrew not found. Install manually:")
        console.print("  https://obsidian.md/download")
        return False

    if plat == "linux":
        if find_executable("snap"):
            return _run_cmd(["sudo", "snap", "install", "obsidian"], "Obsidian via snap")
        console.print("  [yellow]⚠[/yellow] snap not found. Install manually:")
        console.print("  https://obsidian.md/download")
        return False

    if plat == "windows":
        if find_executable("winget"):
            return _run_cmd(["winget", "install", "Obsidian.Obsidian"], "Obsidian via winget")
        console.print("  [yellow]⚠[/yellow] winget not found. Install manually:")
        console.print("  https://obsidian.md/download")
        return False

    return False


# ─── uv ────────────────────────────────────────────────────────────


def install_uv(non_interactive: bool = False, dry_run: bool = False) -> bool:
    """Install uv package manager."""
    if _check_tool("uv"):
        return True

    plat = get_platform()
    if dry_run:
        console.print("  [dim]Would install uv[/dim]")
        return True

    if not _confirm_install("uv", non_interactive):
        return False

    if plat == "macos":
        brew = get_brew_path()
        if brew:
            return _run_cmd([str(brew), "install", "uv"], "uv via Homebrew")
        # Fall back to curl
        return _run_cmd(
            ["bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
            "uv via curl",
        )

    if plat == "linux":
        return _run_cmd(
            ["bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
            "uv via curl",
        )

    if plat == "windows":
        if find_executable("pip"):
            return _run_cmd(
                [sys.executable, "-m", "pip", "install", "uv"],
                "uv via pip",
            )
        console.print(
            "  [yellow]⚠[/yellow] Cannot install uv automatically on Windows without pip."
        )
        console.print("  Install manually: https://docs.astral.sh/uv/getting-started/installation/")
        return False

    return False


# ─── git ───────────────────────────────────────────────────────────


def install_git(non_interactive: bool = False, dry_run: bool = False) -> bool:
    """Install git."""
    if _check_tool("git"):
        return True

    plat = get_platform()
    if dry_run:
        console.print("  [dim]Would install git[/dim]")
        return True

    if not _confirm_install("git", non_interactive):
        return False

    if plat == "macos":
        # macOS: xcode-select includes git, or Homebrew
        brew = get_brew_path()
        if brew:
            return _run_cmd([str(brew), "install", "git"], "git via Homebrew")
        # Try xcode-select (includes git)
        return _run_cmd(
            ["xcode-select", "--install"],
            "Xcode Command Line Tools (includes git)",
            timeout=600,
        )

    if plat == "linux":
        pkg_mgr = detect_package_manager()
        if pkg_mgr == "apt":
            return _run_cmd(["sudo", "apt-get", "install", "-y", "git"], "git via apt")
        if pkg_mgr == "dnf":
            return _run_cmd(["sudo", "dnf", "install", "-y", "git"], "git via dnf")
        if pkg_mgr == "pacman":
            return _run_cmd(["sudo", "pacman", "-S", "--noconfirm", "git"], "git via pacman")

    if plat == "windows" and find_executable("winget"):
        return _run_cmd(["winget", "install", "Git.Git"], "git via winget")

    console.print("  [yellow]⚠[/yellow] Cannot install git automatically. Install manually: https://git-scm.com/")
    return False


# ─── Claude Code ───────────────────────────────────────────────────


def install_claude(non_interactive: bool = False, dry_run: bool = False) -> bool:
    """Install Claude Code CLI via npm."""
    if _check_tool("claude"):
        return True

    if dry_run:
        console.print("  [dim]Would install Claude Code CLI[/dim]")
        return True

    if not _confirm_install("Claude Code CLI", non_interactive):
        return False

    npm = find_executable("npm")
    if not npm:
        console.print("  [yellow]⚠[/yellow] npm not found. Install Node.js first.")
        return False

    return _run_cmd(
        [str(npm), "install", "-g", "@anthropic-ai/claude-code"],
        "Claude Code CLI via npm",
        timeout=120,
    )


# ─── claude-mem ────────────────────────────────────────────────────


def install_claude_mem(non_interactive: bool = False, dry_run: bool = False) -> bool:
    """Install claude-mem plugin via Claude CLI."""
    from obsiforge.utils.platform import get_claude_mem_path

    if get_claude_mem_path():
        return True

    if dry_run:
        console.print("  [dim]Would install claude-mem plugin[/dim]")
        return True

    if not _confirm_install("claude-mem plugin", non_interactive):
        return False

    claude = find_executable("claude")
    if not claude:
        console.print("  [yellow]⚠[/yellow] Claude CLI not found. Install it first.")
        return False

    return _run_cmd(
        [str(claude), "plugin", "install", "claude-mem"],
        "claude-mem plugin",
        timeout=120,
    )


# ─── Installer Registry ───────────────────────────────────────────

INSTALLERS: dict[str, Callable[..., bool]] = {
    "Node.js": install_node,
    "uv": install_uv,
    "git": install_git,
    "Claude Code": install_claude,
    "claude-mem": install_claude_mem,
    "Obsidian": install_obsidian,
}