# ObsiForge

**One command. Three layers. Infinite memory.**

> Built with [Claude Code](https://claude.ai/code). Human-directed, AI-implemented.

ObsiForge sets up the complete Claude Code + Obsidian + Memory integration in a single command. No manual config, no broken MCP servers, no "which plugin do I enable?" moments.

```
obsiforge init --name work --path ~/obsidian-vaults/work
```

That's it. You get:

1. **claude-mem** — Session memory: "how did we fix X bug last time?"
2. **Obsidian vault** — Project knowledge: architecture, decisions, preferences
3. **Semantic search** — Find notes by meaning, not just exact words

---

## 30-Second Install

```bash
# Install
uv tool install git+https://github.com/ssanvi-builds/ObsiForge

# Set up your vault (auto-installs missing prerequisites)
obsiforge init --name work --path ~/obsidian-vaults/work --auto-install

# Open vault in Obsidian → Settings → Community plugins → Enable both plugins
# Then:
cd ~/obsidian-vaults/work && claude
```

**Requirements:** Python >= 3.12 (verify only — manage via pyenv/conda). Other prerequisites (Node.js, Obsidian, uv, git, Claude Code) are auto-installed with `--auto-install`.

## Before / After

### Before ObsiForge

- Manually install 2 Obsidian plugins
- Copy-paste bearer tokens between Obsidian and `.mcp.json`
- Configure REST API ports by hand
- Set up claude-mem hooks in `settings.json`
- Debug MCP connection failures alone
- 45+ minutes of fragile manual setup

### After ObsiForge

```
$ obsiforge init --name work --path ~/obsidian-vaults/work

╭──────────────────────────────────────────────────────────────────────╮
│ ObsiForge v0.1.0                                                     │
│ One-command Claude + Obsidian + Memory integration                   │
╰──────────────────────────────────────────────────────────────────────╯
──────────────────────── Prerequisites ────────────────────────────────
  ✓ Node.js 20.x
  ✓ Python 3.13
  ✓ Obsidian
  ✓ Claude Code
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
─────────────────────── MCP configuration ────────────────────────────
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
│  Layer 2: Obsidian vault                                        │
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

**The rule:** If it helps a *future* session understand the project better → Layer 2. If it's only about *this* session → Layer 1. Layer 3 is just a signpost.

### Semantic Search

MCP Connector includes **Transformers.js** for semantic search — runs entirely inside the Obsidian plugin, no separate server needed.

```
"What did we decide about the database?"  →  Finds decisiones/base-de-datos.md
"how to avoid layout shifts"               →  Finds core-web-vitals.md (CLS section)
"comunicación sin acoplamiento"             →  Finds event-driven-architecture.md
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

### `obsiforge doctor`

```bash
obsiforge doctor              # Run health checks
obsiforge doctor --fix        # Attempt auto-repair
obsiforge doctor --vault work # Check specific vault
```

Checks:
- Obsidian process running
- Global `settings.json` structure (mcpServers, hooks, env)
- Vault files present (CLAUDE.md, MEMORY.md, .mcp.json, plugins)
- Community plugins enabled (mcp-tools, local-rest-api)
- MCP Connector responding + auth
- REST API responding
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
- **Obsidian not running** → Open your vault in Obsidian
- **Plugins not enabled** → Settings → Community plugins → Enable both plugins
- **MCP auth failed** → Bearer token changed; run `obsiforge init` again or update `.mcp.json`
- **claude-mem worker down** → Run `npx claude-mem start` or restart Claude Code
- **Plugin download 403** → Run `gh auth login` first, or set `GITHUB_TOKEN`

### MCP servers not connecting

1. Restart Claude Code session
2. Check `obsiforge doctor --vault <name>` for port conflicts
3. Verify Obsidian is running with the vault open

### Port conflicts

ObsiForge auto-allocates ports starting from:
- REST API: 27124
- MCP HTTP: 27200
- claude-mem worker: 37701

If ports are in use, it finds the next available one. Port reservations are tracked in `~/.claude/obsiforge-state.json` to prevent collisions between vaults.

## Auto-Install

ObsiForge can detect and install missing prerequisites automatically:

```bash
# Interactive — prompts before each install
obsiforge init --name work --path ~/vaults/work --auto-install

# Hands-free — installs everything without prompting
obsiforge init --name work --path ~/vaults/work -y -a
```

### Platform Support

| Tool | macOS (brew) | macOS (no brew) | Linux | Windows |
|------|-------------|-----------------|-------|---------|
| Node.js | fnm → node LTS | fnm (curl) → node LTS | fnm (curl) → node LTS | fnm (winget) → node LTS |
| Obsidian | `brew install --cask obsidian` | Manual download | `snap install obsidian` | `winget install Obsidian.Obsidian` |
| uv | `brew install uv` | curl install script | curl install script | `pip install uv` |
| git | `brew install git` | `xcode-select --install` | apt/dnf/pacman | `winget install Git.Git` |
| Claude Code | `npm install -g @anthropic-ai/claude-code` | same | same | same |
| claude-mem | `claude plugin install claude-mem` | same | same | same |
| Python | Verify only (3.12+) | same | same | same |

> Python is verified but never auto-installed. Manage it via pyenv, conda, or your preferred method.

## Architecture

```
obsiforge/
├── src/obsiforge/
│   ├── cli.py                    # Typer CLI (init, add-vault, doctor, status)
│   ├── doctor.py                 # Health checks + auto-repair
│   ├── phases/
│   │   ├── prerequisites.py      # Phase 0: Check + auto-install deps
│   │   ├── claude_mem.py         # Phase 1: Install claude-mem
│   │   ├── vault.py              # Phase 2: Create/configure vault + download plugins
│   │   ├── mcp_config.py         # Phase 3: Write MCP configs
│   │   └── verify.py             # Phase 4: Health checks
│   ├── utils/
│   │   ├── crypto.py             # API key + bearer token generation
│   │   ├── installer.py          # Platform-aware prerequisite installer
│   │   ├── plugin_downloader.py  # Download plugins from GitHub releases
│   │   ├── ports.py              # Port allocation + collision prevention
│   │   ├── settings_merge.py     # Safe JSON merge with atomic writes
│   │   ├── state.py              # Phase completion tracking
│   │   ├── platform.py           # Cross-platform path + pkg manager detection
│   │   └── prompt.py             # Rich console helpers
├── tests/
│   └── test_smoke.py             # Smoke tests (CLI, imports, live vault)
├── pyproject.toml
└── README.md
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
- [ ] Auto-repair mode (`--fix` actually fixes things)
- [ ] Multi-vault management improvements
- [ ] Obsidian plugin marketplace integration

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)