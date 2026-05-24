"""ObsiForge CLI — one-command Claude + Obsidian + Memory integration."""

from __future__ import annotations

import re

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from obsiforge import __version__
from obsiforge.utils.state import load_state, mark_phase_complete, save_state

app = typer.Typer(
    name="obsiforge",
    help="One-command Claude + Obsidian + Memory integration.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    epilog="Run [bold]obsiforge COMMAND --help[/bold] for more details.",
)

console = Console()

VAULT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_vault_name(name: str) -> str:
    """Validate vault name contains only safe characters."""
    if not VAULT_NAME_PATTERN.match(name):
        console.print(
            f"[bold red]Error:[/bold red] Invalid vault name '{name}'. "
            "Use only letters, numbers, hyphens, and underscores."
        )
        raise typer.Exit(code=1)
    return name


def version_callback(value: bool) -> None:
    if value:
        console.print(f"obsiforge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """ObsiForge — one-command Claude + Obsidian + Memory integration."""


@app.command()
def init(
    vault_name: str = typer.Option(
        ...,
        "--name",
        "-n",
        help="Name for the Obsidian vault (e.g. 'work', 'personal').",
    ),
    vault_path: str = typer.Option(
        ...,
        "--path",
        "-p",
        help="Path where the vault will be created or existing vault path.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would change without touching any file.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "-y",
        help="Accept defaults, no prompts. For scripted installs.",
    ),
    auto_install: bool = typer.Option(
        False,
        "--auto-install",
        "-a",
        help="Automatically install missing prerequisites.",
    ),
) -> None:
    """Set up the full 3-layer memory system.

    Runs 5 phases: prerequisites check, claude-mem install,
    vault configuration, MCP setup, and verification.
    """
    vault_name = _validate_vault_name(vault_name)

    from obsiforge.phases.claude_mem import run as phase1
    from obsiforge.phases.mcp_config import run as phase3
    from obsiforge.phases.prerequisites import run as phase0
    from obsiforge.phases.vault import run as phase2
    from obsiforge.phases.verify import run as phase4

    console.print(
        Panel(
            f"[bold cyan]ObsiForge[/bold cyan] [dim]v{__version__}[/dim]\n"
            "One-command Claude + Obsidian + Memory integration",
            border_style="cyan",
        )
    )

    if dry_run:
        console.print("[bold yellow]DRY RUN MODE[/bold yellow] — no files will be modified.\n")

    # Phase 0: Prerequisites
    console.rule("[bold]Prerequisites[/bold]")
    _prereq_results = phase0(
        vault_name=vault_name,
        vault_path=vault_path,
        dry_run=dry_run,
        non_interactive=non_interactive,
        auto_install=auto_install,
    )

    # Phase 1: claude-mem (global, one-time)
    console.rule("[bold]claude-mem[/bold]")
    _phase1_results = phase1(
        vault_name=vault_name,
        vault_path=vault_path,
        dry_run=dry_run,
        non_interactive=non_interactive,
    )
    if not dry_run:
        mark_phase_complete("claude_mem")

    # Phase 2: Vault setup
    console.rule("[bold]Vault setup[/bold]")
    phase2_results = phase2(
        vault_name=vault_name,
        vault_path=vault_path,
        dry_run=dry_run,
        non_interactive=non_interactive,
    )
    # Save vault state for Phase 3
    if not dry_run:
        state = load_state()
        if vault_name not in state.get("vaults", {}):
            state.setdefault("vaults", {})[vault_name] = {}
        state["vaults"][vault_name].update({
            "rest_api_port": phase2_results.get("rest_api_port"),
            "mcp_http_port": phase2_results.get("mcp_http_port"),
            "api_key": phase2_results.get("api_key"),
            "bearer_token": phase2_results.get("bearer_token"),
            "vault_path": phase2_results.get("vault_path"),
        })
        save_state(state)
        mark_phase_complete("vault", vault_name)

    # Phase 3: MCP configuration
    console.rule("[bold]MCP configuration[/bold]")
    _phase3_results = phase3(
        vault_name=vault_name,
        vault_path=vault_path,
        dry_run=dry_run,
        non_interactive=non_interactive,
        mcp_http_port=phase2_results.get("mcp_http_port"),
        bearer_token=phase2_results.get("bearer_token"),
        api_key=phase2_results.get("api_key"),
    )
    if not dry_run:
        mark_phase_complete("mcp_config", vault_name)

    # Phase 4: Verification
    console.rule("[bold]Verification[/bold]")
    _phase4_results = phase4(
        vault_name=vault_name,
        vault_path=vault_path,
        dry_run=dry_run,
        non_interactive=non_interactive,
    )
    if not dry_run:
        mark_phase_complete("verify", vault_name)

    console.print()
    if dry_run:
        console.print(
            Panel(
                "[bold yellow]DRY RUN COMPLETE[/bold yellow]\n\n"
                "No files were modified. Run without --dry-run to apply changes.",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                "[bold green]Setup complete![/bold green]\n\n"
                "Next steps:\n"
                "1. New vault? Obsidian → Settings → Community plugins → Enable both\n"
                "2. Wait for MCP Connector to start (check Obsidian status bar)\n"
                "3. Restart Claude Code so MCP tools connect\n"
                f"4. cd \"{vault_path}\" && claude\n"
                "5. Run [bold]/dashboard[/bold] to verify",
                border_style="green",
            )
        )


@app.command()
def add_vault(
    vault_name: str = typer.Argument(help="Name for the new vault (e.g. 'work')."),
    vault_path: str = typer.Argument(help="Path for the new vault."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would change without touching any file.",
    ),
) -> None:
    """Add a new vault without redoing global setup.

    Only runs vault-specific phases (2-4). claude-mem
    and global settings are left unchanged.
    """
    vault_name = _validate_vault_name(vault_name)

    from obsiforge.phases.mcp_config import run as phase3
    from obsiforge.phases.vault import run as phase2
    from obsiforge.phases.verify import run as phase4

    console.print(
        Panel(
            f"[bold cyan]Adding vault:[/bold cyan] {vault_name}\n"
            f"[dim]{vault_path}[/dim]",
            border_style="cyan",
        )
    )

    # Phase 2: Vault setup
    console.rule("[bold]Vault setup[/bold]")
    phase2_results = phase2(
        vault_name=vault_name,
        vault_path=vault_path,
        dry_run=dry_run,
        non_interactive=False,
    )

    # Save vault state
    if not dry_run:
        state = load_state()
        if vault_name not in state.get("vaults", {}):
            state.setdefault("vaults", {})[vault_name] = {}
        state["vaults"][vault_name].update({
            "rest_api_port": phase2_results.get("rest_api_port"),
            "mcp_http_port": phase2_results.get("mcp_http_port"),
            "api_key": phase2_results.get("api_key"),
            "bearer_token": phase2_results.get("bearer_token"),
            "vault_path": phase2_results.get("vault_path"),
        })
        save_state(state)
        mark_phase_complete("vault", vault_name)

    # Phase 3: MCP configuration
    console.rule("[bold]MCP configuration[/bold]")
    phase3(
        vault_name=vault_name,
        vault_path=vault_path,
        dry_run=dry_run,
        non_interactive=False,
    )
    if not dry_run:
        mark_phase_complete("mcp_config", vault_name)

    # Phase 4: Verification
    console.rule("[bold]Verification[/bold]")
    phase4(
        vault_name=vault_name,
        vault_path=vault_path,
        dry_run=dry_run,
        non_interactive=False,
    )
    if not dry_run:
        mark_phase_complete("verify", vault_name)

    console.print()
    console.print(
        Panel(
            f"[bold green]Vault '{vault_name}' added![/bold green]\n\n"
            "Next steps:\n"
            "1. Open vault in Obsidian → Settings → Community plugins → Enable both\n"
            f"2. cd \"{vault_path}\" && claude\n"
            "3. Run [bold]/dashboard[/bold] to verify",
            border_style="green",
        )
    )


@app.command()
def doctor(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Attempt to auto-repair found issues.",
    ),
    vault_name: str | None = typer.Option(
        None,
        "--vault",
        help="Vault name to check (defaults to first configured vault).",
    ),
) -> None:
    """Health check all components and auto-repair common issues.

    Checks: Obsidian process, MCP servers, plugins, API keys, ports,
    claude-mem worker, and semantic search index.
    """
    from obsiforge.doctor import run_doctor

    run_doctor(vault_name=vault_name, fix=fix)


@app.command()
def status(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON for scripting.",
    ),
) -> None:
    """Show what's configured and what's missing.

    Displays a rich table of all components with their status:
    installed, configured, running, or missing.
    """
    from obsiforge.phases.verify import get_status

    statuses = get_status()

    if json_output:
        import json

        console.print(json.dumps(statuses, indent=2))
        return

    table = Table(title="ObsiForge Status", show_lines=True)
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    status_style = {
        "ok": "[green]OK[/green]",
        "missing": "[red]MISSING[/red]",
        "partial": "[yellow]PARTIAL[/yellow]",
        "error": "[red bold]ERROR[/red bold]",
        "running": "[green]RUNNING[/green]",
        "stopped": "[yellow]STOPPED[/yellow]",
        "unknown": "[dim]UNKNOWN[/dim]",
        "skipped": "[dim]SKIPPED[/dim]",
    }

    for component, info in statuses.items():
        table.add_row(
            component,
            status_style.get(info["status"], info["status"]),
            info.get("details", ""),
        )

    console.print(table)