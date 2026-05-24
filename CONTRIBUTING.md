# Contributing to ObsiForge

Thanks for your interest! Here's how to contribute.

## Setup

```bash
git clone https://github.com/ssanvi-builds/ObsiForge.git
cd ObsiForge
uv sync
```

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/

# Try it
uv run obsiforge init --name test --path /tmp/test-vault --dry-run
```

## Pull Requests

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make changes with tests
4. Ensure all tests pass: `uv run pytest`
5. Push and open a PR

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add hybrid search with RRF fusion
fix: prevent port collisions between vaults
docs: add troubleshooting section
refactor: remove Smart Connections dependency
```

## Reporting Issues

- **Bug reports**: Include OS, Python version, `obsiforge --version`, and full error output
- **Feature requests**: Describe the problem you're trying to solve, not just the solution

## Code Style

- Python 3.12+ with type hints
- Rich for CLI output, Typer for commands
- Functions < 50 lines, files < 800 lines
- No mutation — prefer creating new objects
- Run `obsiforge doctor` to verify setup

## License

By contributing, you agree that your contributions will be licensed under the MIT License.