"""Download Obsidian community plugin files from GitHub releases."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from rich.console import Console

from obsiforge.utils.prompt import print_dry_run, print_error, print_success, print_warning

console = Console()

PLUGIN_REPOS = {
    "mcp-tools-istefox": "istefox/obsidian-mcp-tools",
    "obsidian-local-rest-api": "coddingtonbear/obsidian-local-rest-api",
}

GITHUB_RELEASE_API = "https://api.github.com/repos/{repo}/releases/latest"
REQUIRED_PLUGIN_FILES = ["main.js", "manifest.json"]
OPTIONAL_PLUGIN_FILES = ["styles.css"]


def _get_github_token() -> str | None:
    """Get GitHub token from env or gh CLI."""
    import os

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token

    try:
        import subprocess
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _fetch_json(url: str) -> dict[str, Any] | None:
    """Fetch JSON from a URL with error handling."""
    try:
        headers = {"User-Agent": "obsiforge"}
        token = _get_github_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return dict(json.loads(resp.read()))
    except Exception as e:
        print_error(f"Failed to fetch {url}: {e}")
        return None


def _download_file(url: str, dest: Path) -> bool:
    """Download a file from URL to local path."""
    try:
        headers = {"User-Agent": "obsiforge"}
        token = _get_github_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as e:
        print_error(f"Failed to download {url}: {e}")
        return False


def download_plugin(plugin_id: str, plugins_dir: Path, dry_run: bool = False) -> bool:
    """Download plugin files (main.js, manifest.json) from GitHub latest release.

    Args:
        plugin_id: Obsidian plugin ID (e.g. 'mcp-tools-istefox').
        plugins_dir: Path to .obsidian/plugins/ directory.
        dry_run: If True, show what would be downloaded.

    Returns:
        True if all required files were downloaded (or dry-run).
    """
    repo = PLUGIN_REPOS.get(plugin_id)
    if not repo:
        print_warning(f"Unknown plugin repo for {plugin_id}, skipping download")
        return False

    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Check if plugin files already exist
    if (plugin_dir / "main.js").exists() and (plugin_dir / "manifest.json").exists():
        print_success(f"{plugin_id} already installed, skipping download")
        return True

    if dry_run:
        print_dry_run(f"Would download {plugin_id} from github.com/{repo}")
        return True

    # Fetch latest release info from GitHub
    api_url = GITHUB_RELEASE_API.format(repo=repo)
    release = _fetch_json(api_url)
    if not release:
        print_error(f"Could not fetch release info for {plugin_id}")
        return False

    # Build asset lookup
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}

    success = True
    for filename in REQUIRED_PLUGIN_FILES + OPTIONAL_PLUGIN_FILES:
        if filename not in assets:
            if filename in REQUIRED_PLUGIN_FILES:
                print_error(f"{filename} not found in {plugin_id} release")
                success = False
            continue

        dest = plugin_dir / filename
        if _download_file(assets[filename], dest):
            print_success(f"Downloaded {plugin_id}/{filename}")

    if success:
        version = release.get("tag_name", "unknown")
        print_success(f"{plugin_id} v{version} installed")

    return success


def download_all_plugins(vault_path: Path, dry_run: bool = False) -> list[str]:
    """Download all required Obsidian plugins.

    Args:
        vault_path: Path to the vault root.
        dry_run: If True, show what would be downloaded.

    Returns:
        List of plugin IDs that were successfully installed.
    """
    plugins_dir = vault_path / ".obsidian" / "plugins"

    installed = []
    for plugin_id in PLUGIN_REPOS:
        if download_plugin(plugin_id, plugins_dir, dry_run):
            installed.append(plugin_id)

    return installed