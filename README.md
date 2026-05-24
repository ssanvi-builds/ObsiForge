# ObsiForge

[![X](https://img.shields.io/badge/@ssanvi_builds-000000?logo=x&style=for-the-badge)](https://x.com/ssanvi_builds)

**One command + 2 clicks. Three layers. Infinite memory.**

> claude code · obsidian · mcp server · semantic search · ai memory · knowledge management · developer tools · llm integration

> Built with [Claude Code](https://claude.ai/code). Human-directed, AI-implemented.

ObsiForge sets up the complete Claude Code + Obsidian + Memory integration in a single command. No manual config, no broken MCP servers, no "which plugin do I enable?" moments.

```
obsiforge init --name work --path ~/obsidian-vaults/work
```

Then enable 2 plugins in Obsidian Settings. That's it. You get:

1. **claude-mem** — Session memory: "how did we fix X bug last time?"
2. **Obsidian vault + semantic search** — Project knowledge, searchable by meaning
3. **Native memory** — Pointer only, keeps Claude focused

---

## Installation

### Prerequisites

| Requirement | Minimum Version | Auto-installed? |
|-------------|----------------|:---:|
| Python | 3.12+ | No — verify only |
| Node.js | 18+ | Yes (via fnm) |
| Obsidian | latest | Yes |
| Claude Code | latest | Yes (via npm) |
| uv | latest | Yes |
| git | latest | Yes |
| claude-mem | latest | Yes (via `claude plugin install`) |

Python is **verified but never auto-installed**. Manage it via pyenv, conda, or your preferred method.

### macOS

```bash
# Option 1: Install via uv (recommended)
uv tool install git+https://github.com/ssanvi-builds/ObsiForge

# Option 2: Install via pipx
pipx install git+https://github.com/ssanvi-builds/ObsiForge

# Option 3: Clone and develop
git clone https://github.com/ssanvi-builds/ObsiForge.git
cd ObsiForge
uv sync
uv run obsiforge init --name work --path ~/obsidian-vaults/work

# Set up your vault (auto-installs missing prerequisites)
obsiforge init --name work --path ~/obsidian-vaults/work --auto-install

# Enable community plugins in Obsidian:
# Settings → Community plugins → Turn on → Enable both plugins
# Then:
cd ~/obsidian-vaults/work && claude
```

### Linux

```bash
# Install
uv tool install git+https://github.com/ssanvi-builds/ObsiForge

# Set up your vault
obsiforge init --name work --path ~/obsidian-vaults/work --auto-install

# If Obsidian isn't installed, auto-install uses snap:
# sudo snap install obsidian
# Or download manually from https://obsidian.md/download

# Enable community plugins, then:
cd ~/obsidian-vaults/work && claude
```

### Windows

```powershell
# Install
uv tool install git+https://github.com/ssanvi-builds/ObsiForge

# Set up your vault
obsiforge init --name work --path "%USERPROFILE%\obsidian-vaults\work" --auto-install

# If Obsidian isn't installed, auto-install uses winget:
# winget install Obsidian.Obsidian

# Enable community plugins, then:
cd "%USERPROFILE%\obsidian-vaults\work" && claude
```

### Non-interactive / CI

```bash
# Hands-free: installs everything without prompting
obsiforge init --name work --path ~/obsidian-vaults/work -y -a

# Dry-run: preview changes without writing files
obsiforge init --name work --path ~/obsidian-vaults/work --dry-run
```

## Before / After

### Before ObsiForge

- Manually install 2 Obsidian plugins
- Copy-paste bearer tokens between Obsidian and `.mcp.json`
- Configure REST API ports by hand
- Set up claude-mem hooks in `settings.json`
- Debug MCP connection failures alone
- Re-do everything when tokens expire or plugins update
- 45+ minutes of fragile manual setup

### After ObsiForge

```
$ obsiforge init --name work --path ~/obsidian-vaults/work

╭──────────────────────────────────────────────────────────────────────╮
│ ObsiForge v0.1.0                                                     │
│ One-command Claude + Obsidian + Memory integration                   │
╰──────────────────────────────────────────────────────────────────────╯
──────────────────────── Prerequisites ────────────────────────────────
  ✓ Node.js 26.x
  ✓ Python 3.13
  ✓ Obsidian
  ✓ Claude Code
  ✓ uv
  ✓ git
  ✓ claude-mem
─────────────────────────── claude-mem ────────────────────────────────
  ✓ claude-mem plugin installed
  ✓ SessionStart hook configured
  ✓ Stop hook configured
─────────────────────────── Vault setup ───────────────────────────────
  ✓ Directory structure created
  ✓ Plugins downloaded from GitHub
  ✓ CLAUDE.md written
  ✓ MEMORY.md written
  ✓ Community plugins configured (2/2)
  ✓ REST API configured (port 27124)
  ✓ MCP Connector configured (port 27200)
─────────────────────── MCP configuration ──────────────────────────────
  ✓ .mcp.json written
  ✓ settings.local.json written
────────────────────────── Verification ──────────────────────────────
  ✓ claude-mem worker: healthy
  ✓ MCP Connector: responding on port 27200
  ✓ REST API: responding on port 27124
  ✓ All vault files present

╭──────────────────────────────────────────────────────────────────────╮
│ Setup complete!                                                      │
│                                                                      │
│ Next steps:                                                          │
│ 1. Obsidian → Settings → Community plugins → Enable both            │
│ 2. Wait for MCP Connector to start (check Obsidian status bar)      │
│ 3. Restart Claude Code so MCP tools connect                         │
│ 4. cd ~/obsidian-vaults/work && claude                              │
│ 5. Run /dashboard to verify                                         │
╰──────────────────────────────────────────────────────────────────────╯
```

## Commands

| Command | Description |
|---------|-------------|
| `obsiforge init` | Full setup (prerequisites → verify) |
| `obsiforge add-vault` | Add a new vault without redoing global setup |
| `obsiforge doctor` | Health check + auto-repair |
| `obsiforge status` | Show what's configured and what's missing |
| `obsiforge --version` | Show version |

## Daily Workflow

```
# Start of session
cd ~/obsidian-vaults/work
claude
/dashboard          # Load vault context, check system health

# ... work normally ...
# Claude reads/writes vault via MCP tools automatically

# End of session
/consolidate         # Distill session observations into vault notes
```

**Session lifecycle:**
1. `/dashboard` — Orient: read user profile, project status, recent work
2. Work — Claude uses MCP tools to search/read/write the vault
3. `/consolidate` — Save what matters from this session into vault notes

**Key skills:**
- `/dashboard` — Session start briefing
- `/consolidate` — Session end: claude-mem → vault
- `/mem-search` — Search claude-mem observations

## How It Works

### 3-Layer Memory

Each layer has a different purpose. **Never duplicate knowledge across layers.**

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 1: claude-mem                                            │
│  What: Session observations — "how did we fix that bug?"       │
│  Where: SQLite + ChromaDB (~/.claude-mem/)                     │
│  How to search: /mem-search or claude-mem MCP tools             │
│  Lifecycle: Automatic — hooks capture every session             │
│  Example: "Tried approach X, failed, approach Y worked"       │
├──────────────────────────────────────────────────────────────────┤
│  Layer 2: Obsidian vault + semantic search                      │
│  What: Project knowledge — decisions, preferences, architecture  │
│  Where: Claude/ folder in vault                                │
│  How to search: search_vault_smart (semantic) or                │
│                 search_vault_simple (exact text)                 │
│  Lifecycle: Manual — /consolidate at end of session             │
│  Example: "We chose PostgreSQL over MongoDB for Atalaya         │
│            because we need relational queries and ACID"          │
├──────────────────────────────────────────────────────────────────┤
│  Layer 3: Claude native memory                                  │
│  What: Pointer only — "Use MCP tools to read the vault"        │
│  Where: memory/MEMORY.md                                       │
│  How to search: Don't — it's just an index                     │
│  Lifecycle: Written once by obsiforge init                      │
│  Example: "Project knowledge lives in the vault. See MEMORY.md" │
└──────────────────────────────────────────────────────────────────┘
```

**The rule:** If it helps a *future* session understand the project better → Layer 2. If it's only about *this* session → Layer 1. Layer 3 is just a signpost, never store knowledge there.

### Multi-Vault Support

Each vault gets its own ports, MCP config, and memory. Zero collisions.

```bash
obsiforge init --name prism --path ~/obsidian-vaults/prism
obsiforge init --name atalaya --path ~/obsidian-vaults/atalaya

obsiforge doctor --vault prism
obsiforge doctor --vault atalaya
```

Ports are auto-allocated and tracked in `~/.claude/obsiforge-state.json` to prevent collisions.

### Semantic Search

MCP Connector includes **Transformers.js** for semantic search — runs entirely inside the Obsidian plugin, no separate server needed.

```
"What did we decide about the database?"  →  Finds decisions/database-choices.md
"how to avoid layout shifts"               →  Finds core-web-vitals.md (CLS section)
"event-driven decoupled communication"    →  Finds event-driven-architecture.md
```

Search hierarchy:
1. **`search_vault_smart`** — Semantic. Find notes by meaning, not exact words
2. **`search_vault_simple`** — Exact text. For when you know the specific term
3. **`get_vault_file`** — Direct read when you know the exact file path

**Tip:** Use smart search to explore, simple search to confirm. Together they cover more ground than either alone.

### 2 Obsidian Plugins

| Plugin | Purpose | Auto-downloaded? |
|--------|---------|:---:|
| **MCP Connector** (mcp-tools-istefox) | MCP server + semantic search | Yes |
| **Local REST API** | REST endpoint for vault operations | Yes |

Both plugins are downloaded from GitHub releases during `obsiforge init`. Uses `gh auth token` or `GITHUB_TOKEN` if available to avoid rate limits.

## Command Reference

### `obsiforge init`

```bash
obsiforge init --name work --path ~/obsidian-vaults/work
obsiforge init --name personal --path ~/obsidian-vaults/personal --dry-run
obsiforge init --name work --path ~/obsidian-vaults/work -y          # non-interactive
obsiforge init --name work --path ~/obsidian-vaults/work -a          # auto-install deps
obsiforge init --name work --path ~/obsidian-vaults/work -y -a       # hands-free
```

Options:
- `--name, -n` — Vault name (required, alphanumeric + hyphens/underscores only)
- `--path, -p` — Vault path (required)
- `--dry-run` — Preview changes without writing files
- `--non-interactive, -y` — Accept all defaults
- `--auto-install, -a` — Automatically install missing prerequisites

### `obsiforge add-vault`

```bash
obsiforge add-vault work ~/obsidian-vaults/work
obsiforge add-vault personal ~/obsidian-vaults/personal --dry-run
```

Adds a new vault without redoing global setup (claude-mem and global settings are left unchanged). Only runs vault-specific phases 2–4.

### `obsiforge doctor`

```bash
obsiforge doctor              # Run health checks
obsiforge doctor --fix        # Attempt auto-repair
obsiforge doctor --vault work # Check specific vault
```

Checks (9 total):
- Obsidian process running (cross-platform: pgrep/tasklist)
- Global `settings.json` structure (mcpServers, hooks, env)
- Vault files present (CLAUDE.md, MEMORY.md, user-preferences.md, .mcp.json, plugins)
- Workspace.json exists
- Community plugins enabled (2/2)
- MCP Connector responding + auth
- REST API responding (detects actual port if different from expected)
- claude-mem worker healthy

### `obsiforge status`

```bash
obsiforge status          # Rich table output
obsiforge status --json   # JSON for scripting
```

## Troubleshooting

### `obsiforge doctor` reports issues

```bash
obsiforge doctor              # See what's wrong
obsiforge doctor --fix        # Attempt auto-repair
```

Common fixes:
- **Obsidian not running** → `obsiforge init` will auto-launch Obsidian (quit-modify-launch strategy)
- **Plugins not enabled** → Settings → Community plugins → Turn on → Enable both plugins (Obsidian security requirement)
- **MCP auth failed** → Bearer token changed; run `obsiforge init` again or update `.mcp.json`
- **MCP auth failed on non-active vault** → Expected: Obsidian runs one vault at a time. Switch vaults in Obsidian and re-check.
- **claude-mem worker down** → Run `npx claude-mem start` or restart Claude Code
- **Plugin download 403** → Run `gh auth login` first, or set `GITHUB_TOKEN`

### MCP servers not connecting

1. Restart Claude Code session
2. Check `obsiforge doctor --vault <name>` for port conflicts
3. Verify Obsidian is running with the vault open

### Port conflicts

ObsiForge auto-allocates ports starting from:
- REST API: 27124
- MCP HTTP: 27200 (range 27200–27210)
- claude-mem worker: 37701

If ports are in use, it finds the next available one. Port reservations are tracked in `~/.claude/obsiforge-state.json` to prevent collisions between vaults.

### "Community plugins" toggle keeps turning off

This is expected on first launch. After running `obsiforge init`:
1. Open Obsidian → Settings → Community plugins
2. Click **Turn on community plugins** (trust dialog)
3. Enable each plugin toggle (MCP Tools, Local REST API)
4. Restart Obsidian or reload (Cmd+R on macOS)

## Auto-Install

ObsiForge can detect and install missing prerequisites automatically:

```bash
# Interactive — prompts before each install
obsiforge init --name work --path ~/vaults/work --auto-install

# Hands-free — installs everything without prompting
obsiforge init --name work --path ~/vaults/work -y -a
```

### Platform Support

| Tool | macOS (Homebrew) | macOS (no Homebrew) | Linux | Windows |
|------|-----------------|---------------------|-------|---------|
| Node.js | fnm → Node LTS | fnm (curl) → Node LTS | fnm (curl) → Node LTS | fnm (winget) → Node LTS |
| Obsidian | `brew install --cask obsidian` | Manual download | `snap install obsidian` | `winget install Obsidian.Obsidian` |
| uv | `brew install uv` | curl install script | curl install script | `pip install uv` |
| git | `brew install git` | `xcode-select --install` | apt/dnf/pacman | `winget install Git.Git` |
| Claude Code | `npm install -g @anthropic-ai/claude-code` | same | same | same |
| claude-mem | `claude plugin install claude-mem` | same | same | same |
| Python | Verify only (3.12+) | same | same | same |

## Architecture

```
obsiforge/
├── src/obsiforge/
│   ├── cli.py                    # Typer CLI (init, add-vault, doctor, status)
│   ├── doctor.py                 # Health checks + auto-repair
│   ├── phases/
│   │   ├── prerequisites.py      # Phase 0: Check + auto-install deps
│   │   ├── claude_mem.py         # Phase 1: Install claude-mem + hooks
│   │   ├── vault.py              # Phase 2: Create/configure vault + plugins
│   │   ├── mcp_config.py         # Phase 3: Write MCP configs
│   │   └── verify.py             # Phase 4: Health checks
│   ├── utils/
│   │   ├── crypto.py             # API key + bearer token generation
│   │   ├── installer.py          # Platform-aware prerequisite installer
│   │   ├── obsidian.py           # Cross-platform Obsidian detection + port discovery
│   │   ├── plugin_downloader.py  # Download plugins from GitHub releases
│   │   ├── ports.py              # Port allocation + collision prevention
│   │   ├── prompt.py             # Rich console helpers + interactive prompts
│   │   ├── settings_merge.py     # Safe JSON merge with atomic writes
│   │   ├── state.py              # Phase completion tracking
│   │   └── platform.py           # Cross-platform path + executable detection
├── tests/
│   ├── conftest.py               # Shared fixtures (mock Obsidian interactions)
│   ├── test_cli.py               # CLI argument parsing
│   ├── test_crypto.py            # API key + bearer token generation
│   ├── test_doctor.py            # Health check logic
│   ├── test_integration.py       # End-to-end vault init
│   ├── test_ports.py             # Port allocation + collision prevention
│   ├── test_settings_merge.py    # Safe JSON merge
│   ├── test_smoke.py             # Smoke tests (CLI, imports, live vault)
│   ├── test_state.py             # Phase completion tracking
│   └── test_bm25.py              # BM25 search integration (requires Node.js)
├── pyproject.toml
└── README.md
```

## Development

```bash
# Clone and set up
git clone https://github.com/ssanvi-builds/ObsiForge.git
cd ObsiForge
uv sync

# Run tests (full suite)
uv run pytest tests/ -v

# Run tests excluding Node.js-dependent tests
uv run pytest tests/ -v --ignore=tests/test_bm25.py

# Lint
uv run ruff check src/

# Type check
uv run mypy src/

# Try it
uv run obsiforge init --name test --path /tmp/test-vault --dry-run
```

## Roadmap

- [x] CLI skeleton (`init`, `add-vault`, `doctor`, `status`)
- [x] Full init flow (5 phases: prerequisites → verify)
- [x] Plugin auto-download from GitHub releases
- [x] Semantic search via MCP Connector (Transformers.js, always current)
- [x] Doctor command (health check + diagnostics)
- [x] Auto-install prerequisites (`--auto-install` / `-a`)
- [x] Port collision prevention across vaults
- [x] GitHub token auth for plugin downloads
- [x] Reliable vault opening (quit-modify-launch strategy)
- [x] MCP Connector port discovery (actual port, not allocated)
- [x] Multi-vault doctor with `--vault` selection
- [x] Dark theme default (appearance.json)
- [ ] Auto-repair mode (`--fix` actually fixes things)
- [ ] Test isolation (state file shared with pytest)
- [ ] Obsidian plugin marketplace integration

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)