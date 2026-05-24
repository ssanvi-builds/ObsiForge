"""Interactive prompts with rich styling."""

from __future__ import annotations

import questionary
from rich.console import Console

console = Console()


def confirm(message: str, default: bool = True) -> bool:
    """Ask a yes/no question with rich formatting.

    Args:
        message: The question to ask.
        default: Default value if user presses Enter.

    Returns:
        True for yes, False for no.
    """
    result = questionary.confirm(message, default=default).ask()
    return result if result is not None else default


def print_step(step: str, detail: str = "") -> None:
    """Print a step indicator with optional detail."""
    if detail:
        console.print(f"  [bold cyan]→[/bold cyan] {step}: {detail}")
    else:
        console.print(f"  [bold cyan]→[/bold cyan] {step}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"  [green]✓[/green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"  [yellow]⚠[/yellow] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"  [red]✗[/red] {message}")


def print_dry_run(message: str) -> None:
    """Print a dry-run indicator."""
    console.print(f"  [dim][DRY RUN][/dim] {message}")