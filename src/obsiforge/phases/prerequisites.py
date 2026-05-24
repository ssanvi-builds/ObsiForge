"""Phase 0: Check and install prerequisites (Node.js, Python, Obsidian, Claude Code, uv, git)."""

from __future__ import annotations

import re
import subprocess

from rich.console import Console
from rich.table import Table

from obsiforge.utils.installer import INSTALLERS
from obsiforge.utils.platform import (
    expand_path,
    find_executable,
    get_claude_path,
    get_git_path,
    get_node_path,
    get_obsidian_path,
    get_platform,
    get_python_path,
    get_uv_path,
)
from obsiforge.utils.prompt import confirm, print_error, print_success, print_warning

console = Console()

MIN_NODE_VERSION = 18
MIN_PYTHON_VERSION = (3, 12)

# Hard requirements that block init if missing
HARD_REQUIREMENTS = ["Node.js >= 18", "Python >= 3.12", "Obsidian", "Claude Code", "uv", "git"]

# Tools that can be auto-installed
AUTO_INSTALLABLE = ["Node.js >= 18", "Obsidian", "Claude Code", "uv", "git", "claude-mem"]

# Map check names to installer function names in INSTALLERS
INSTALLER_MAP = {
    "Node.js >= 18": "Node.js",
    "Obsidian": "Obsidian",
    "Claude Code": "Claude Code",
    "uv": "uv",
    "git": "git",
    "claude-mem": "claude-mem",
}


def _get_version(cmd: str) -> str | None:
    """Get version string from a command."""
    try:
        result = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout + result.stderr).strip()
        return output
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _parse_major_version(version_str: str) -> int | None:
    """Extract major version number from a version string."""
    match = re.search(r"(\d+)", version_str)
    return int(match.group(1)) if match else None


def _check_node() -> tuple[bool, str]:
    """Check Node.js version >= 18."""
    path = get_node_path()
    if not path:
        return False, "not found — can auto-install via fnm"

    version = _get_version("node")
    if not version:
        return True, f"found at {path} (version unknown)"

    major = _parse_major_version(version)
    if major and major < MIN_NODE_VERSION:
        return False, f"version {version} (need >= {MIN_NODE_VERSION})"

    return True, f"version {version}"


def _check_python() -> tuple[bool, str]:
    """Check Python version >= 3.12."""
    path = get_python_path()
    if not path:
        return False, "not found — install from https://python.org"

    version = _get_version("python3") or _get_version("python")
    if not version:
        return True, f"found at {path} (version unknown)"

    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", version)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        if (major, minor) < MIN_PYTHON_VERSION:
            return False, f"version {version} (need >= {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]})"

    return True, f"version {version}"


def _check_obsidian() -> tuple[bool, str]:
    """Check if Obsidian is installed."""
    path = get_obsidian_path()
    if path:
        return True, f"found at {path}"
    # Obsidian might be running without being in PATH
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Obsidian"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, "running (found process)"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False, "not found — can auto-install via Homebrew"


def _check_claude() -> tuple[bool, str]:
    """Check if Claude Code CLI is installed."""
    path = get_claude_path()
    if not path:
        return False, "not found — can auto-install via npm"
    version = _get_version("claude")
    return True, f"found at {path} {version or ''}"


def _check_uv() -> tuple[bool, str]:
    """Check if uv is installed."""
    path = get_uv_path()
    if not path:
        return False, "not found — can auto-install"
    version = _get_version("uv")
    return True, f"found at {path} {version or ''}"


def _check_git() -> tuple[bool, str]:
    """Check if git is installed."""
    path = get_git_path()
    if not path:
        return False, "not found — can auto-install"
    version = _get_version("git")
    return True, f"found at {path} {version or ''}"


def _check_claude_mem() -> tuple[bool, str]:
    """Check if claude-mem plugin is already installed."""
    from obsiforge.utils.platform import get_claude_config_dir

    config_dir = get_claude_config_dir()
    mem_path = config_dir / "plugins" / "marketplaces" / "thedotmack" / "plugin"
    if mem_path.exists():
        return True, "already installed"
    return False, "not installed — will install in Phase 1"


def run(
    vault_name: str,
    vault_path: str,
    dry_run: bool = False,
    non_interactive: bool = False,
    auto_install: bool = False,
) -> dict:
    """Check all prerequisites and offer to install missing items.

    Args:
        vault_name: Name for the vault (for context).
        vault_path: Path for the vault (for context).
        dry_run: If True, show what would be installed without installing.
        non_interactive: If True, accept defaults without prompting.
        auto_install: If True, automatically install missing prerequisites.

    Returns:
        Dict with check results for downstream phases.
    """
    checks = [
        ("Node.js >= 18", _check_node),
        ("Python >= 3.12", _check_python),
        ("Obsidian", _check_obsidian),
        ("Claude Code", _check_claude),
        ("uv", _check_uv),
        ("git", _check_git),
        ("claude-mem", _check_claude_mem),
    ]

    # First pass: check all prerequisites
    results = {}
    for name, check_fn in checks:
        found, details = check_fn()
        results[name] = {"found": found, "details": details}

    # Display initial results
    table = Table(title="Prerequisites", show_lines=True)
    table.add_column("Requirement", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    for name, check_fn in checks:
        info = results[name]
        if info["found"]:
            table.add_row(name, "[green]OK[/green]", info["details"])
        else:
            table.add_row(name, "[red]MISSING[/red]", info["details"])

    console.print(table)

    # Check for missing items
    missing = [name for name, info in results.items() if not info["found"]]

    if not missing:
        print_success("All required prerequisites met.")
        return results

    # Offer to install missing items
    console.print()
    missing_hard = [name for name in HARD_REQUIREMENTS if not results.get(name, {}).get("found")]

    if missing_hard:
        console.print(f"[bold yellow]Missing prerequisites: {', '.join(missing_hard)}[/bold yellow]")

        # Try auto-install for missing items
        installed_any = False
        for name in missing:
            installer_name = INSTALLER_MAP.get(name)
            if not installer_name or installer_name not in INSTALLERS:
                # Python cannot be auto-installed
                continue

            installer_fn = INSTALLERS[installer_name]

            if auto_install or (non_interactive and name in AUTO_INSTALLABLE):
                console.print(f"\n[bold]Installing {name}...[/bold]")
                success = installer_fn(non_interactive=True, dry_run=dry_run)
                if success and not dry_run:
                    # Re-check
                    for check_name, check_fn in checks:
                        if check_name == name:
                            found, details = check_fn()
                            results[name] = {"found": found, "details": details}
                            if found:
                                print_success(f"{name} installed successfully: {details}")
                                installed_any = True
                            else:
                                print_error(f"{name} installation did not resolve the issue")
            elif not non_interactive:
                if confirm(f"  Install {name}?", default=True):
                    console.print(f"\n[bold]Installing {name}...[/bold]")
                    success = installer_fn(non_interactive=False, dry_run=dry_run)
                    if success and not dry_run:
                        for check_name, check_fn in checks:
                            if check_name == name:
                                found, details = check_fn()
                                results[name] = {"found": found, "details": details}
                                if found:
                                    print_success(f"{name} installed: {details}")
                                    installed_any = True

        # Final check after installations
        still_missing = [name for name in HARD_REQUIREMENTS if not results.get(name, {}).get("found")]
        if still_missing:
            console.print(f"\n[bold red]Still missing: {', '.join(still_missing)}[/bold red]")
            console.print("Install them manually before running obsiforge init again.")
            if "Python >= 3.12" in still_missing:
                console.print("[dim]  Python: Install from https://python.org or via pyenv[/dim]")
            raise SystemExit(1)

        if installed_any:
            print_success("All prerequisites installed successfully.")
    else:
        # Only optional items missing (claude-mem)
        print_warning("Some optional components are missing. They will be installed automatically.")

    print_success("All required prerequisites met.")
    return results