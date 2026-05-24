# ObsiForge

**One command. Three layers. Infinite memory.**

ObsiForge sets up the complete Claude Code + Obsidian + Memory integration in a single command. No manual config, no broken MCP servers, no "which plugin do I enable?" moments.

```
obsiforge init --name work --path ~/obsidian-vaults/work
```

That's it. You get:

1. **claude-mem** — Persistent session memory (SQLite + Chroma)
2. **Obsidian vault** — Knowledge base with MCP read/write/search tools
3. **Semantic search** — MCP Connector's built-in Transformers.js (always up to date, re-indexes on every query)

---

## 30-Second Install

```bash
# Install
uv tool install git+https://github.com/ssanvi/obsiforge

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
│ 3. Restart Claude Code so MCP tools connect                        │
│ 4. cd ~/obsidian-vaults/work && claude                               │
│ 5. Run /dashboard to verify                                         │
╰──────────────────────────────────────────────────────────────────────╯
```

## Commands

| Command | Description |
|---------|-------------|
| `obsiforge init` | Full 3-layer setup (prerequisites → verify) |
| `obsiforge add-vault` | Add a new vault without redoing global setup |
| `obsiforge doctor` | Health check + auto-repair for all components |
| `obsiforge status` | Show what's configured and what's missing |
| `obsiforge --version` | Show version |

### `obsiforge init`

```bash
obsiforge init --name work --path ~/obsidian-vaults/work
obsiforge init --name personal --path ~/obsidian-vaults/personal --dry-run
obsiforge init --name work --path ~/obsidian-vaults/work -y          # non-interactive
obsiforge init --name work --path ~/obsidian-vaults/work -a          # auto-install deps
obsiforge init --name work --path ~/obsidian-vaults/work -y -a       # hands-free setup
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

## How It Works

### 3-Layer Memory Architecture

```
┌──────────────────────────────────────────────────┐
│  Layer 1: claude-mem                            │
│  Session observations, "how did we fix X?"      │
│  SQLite + ChromaDB (~/.claude-mem/)             │
├──────────────────────────────────────────────────┤
│  Layer 2: Obsidian vault                        │
│  Project knowledge, user preferences, decisions  │
│  Claude/ folder in vault                        │
├──────────────────────────────────────────────────┤
│  Layer 3: Claude native memory                  │
│  Pointer only — "Use MCP tools to read vault"   │
│  memory/MEMORY.md                               │
└──────────────────────────────────────────────────┘
```

- **New knowledge** → Obsidian vault (Layer 2) via `create_vault_file` / `patch_vault_file`
- **Session observations** → claude-mem (Layer 1) automatically via hooks
- **Claude native** → pointer only, never stores knowledge directly

### Semantic Search

ObsiForge uses the **MCP Connector's built-in Transformers.js** for semantic search. This runs entirely inside the Obsidian plugin — no separate MCP server, no stale indexes.

**Why not Smart Connections MCP?** Smart Connections' Obsidian plugin indexes fine, but its MCP server reads embeddings once at startup and caches them in memory. New notes don't appear until you restart the MCP server. MCP Connector's `search_vault_smart` re-indexes on every query, so it's always up to date.

Search hierarchy:
1. **`search_vault_smart`** — Primary. Transformers.js embeddings, always current
2. **`search_vault_simple`** — Fallback. Substring search for exact matches
3. **`get_vault_file`** — Direct read when you know the exact file

### 2 Required Obsidian Plugins

| Plugin | Purpose |
|--------|---------|
| **MCP Connector** (mcp-tools-istefox) | MCP server + semantic search via Transformers.js |
| **Local REST API** | REST endpoint for vault file operations |

Both plugins are downloaded from GitHub releases during `obsiforge init` — no manual downloads needed.

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

### MCP servers not connecting

1. Restart Claude Code session
2. Check `obsiforge doctor --vault <name>` for port conflicts
3. Verify Obsidian is running with the vault open

### Port conflicts

ObsiForge auto-allocates ports starting from:
- REST API: 27124
- MCP HTTP: 27200
- claude-mem worker: 37701

If ports are in use, it finds the next available one automatically. Port reservations are tracked in `~/.claude/obsiforge-state.json` to prevent collisions between vaults.

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
- [x] Doctor command (health check + auto-repair)
- [x] Auto-install prerequisites (`--auto-install` / `-a`)
- [x] Port collision prevention across vaults
- [ ] Auto-repair mode (`--fix` actually fixes things)
- [ ] Multi-vault management improvements
- [ ] Obsidian plugin marketplace integration

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)