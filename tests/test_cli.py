"""Tests for ObsiForge CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from obsiforge.cli import app

runner = CliRunner()


def test_version():
    """obsiforge --version prints version and exits."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_help():
    """obsiforge --help shows all commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout
    assert "add-vault" in result.stdout
    assert "doctor" in result.stdout
    assert "status" in result.output


def test_init_help():
    """obsiforge init --help shows options."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "--name" in result.stdout
    assert "--path" in result.stdout
    assert "--dry-run" in result.stdout


def test_add_vault_help():
    """obsiforge add-vault --help shows arguments."""
    result = runner.invoke(app, ["add-vault", "--help"])
    assert result.exit_code == 0
    assert "VAULT_NAME" in result.stdout


def test_doctor():
    """obsiforge doctor runs health checks."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_status():
    """obsiforge status shows table."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_status_json():
    """obsiforge status --json outputs valid JSON."""
    import json

    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "claude-mem" in data