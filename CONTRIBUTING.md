# Contributing to ObsiForge

Thanks for your interest! Here's how to get started.

## Development Setup

```bash
# Clone and enter the repo
git clone https://github.com/ssanvi/obsiforge.git
cd obsiforge

# Create venv and install in editable mode
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Install the search MCP dependencies
cd src/obsiforge/search && npm install && npm run build && cd ../../..

# Run tests
pytest tests/ -v
```

## Project Structure

- `src/obsiforge/` — Python CLI and phases
- `src/obsiforge/search/` — TypeScript MCP search server
- `tests/` — Python tests (CLI + utils)

## Making Changes

1. Create a branch: `git checkout -b feat/your-feature`
2. Make your changes
3. Add tests for new functionality
4. Run `pytest tests/ -v` and ensure all pass
5. Open a pull request

## Code Style

- **Python**: Follow PEP 8. Use type hints. Keep functions under 50 lines.
- **TypeScript**: Follow the existing patterns in `search/src/`.
- **Commits**: Use conventional commits (`feat:`, `fix:`, `chore:`, `docs:`).

## Reporting Issues

Open a GitHub issue with:
- ObsiForge version (`obsiforge --version`)
- OS and Python version
- Full output of `obsiforge doctor`
- Steps to reproduce

## License

By contributing, you agree your code will be licensed under the MIT License.