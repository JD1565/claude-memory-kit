# Claude Memory Kit

Portable starter kit that gives Claude Code persistent memory across sessions. Packages the hooks, scripts, commands, and conventions needed for session continuity, decision tracking, and cross-project learning.

## Project Structure

```
claude-memory-kit/
├── install.sh                    # Interactive installer (creates workspace, merges hooks)
├── README.md                     # Public-facing docs (architecture, quick start, FAQ)
├── GUIDE.md                      # Complete user guide (setup, usage, permissions reference)
├── CHANGELOG.md                  # Session history
├── scripts/
│   ├── memory_db.py              # Core DB module (schema, CRUD, @_safe decorator)
│   ├── hook_session_start.py     # SessionStart — context injection from DB
│   ├── hook_pre_compact.py       # PreCompact — state snapshot before compression
│   ├── hook_stop.py              # Stop — keyword-gated decision/learning extraction
│   ├── hook_post_tool_use.py     # PostToolUse — git commit tracking
│   └── get_session_info.py       # Helper for /save (session start time lookup)
├── commands/
│   ├── save.md                   # /save — end-of-session full save
│   ├── checkpoint.md             # /checkpoint — mid-session lightweight save
│   ├── understand.md             # /understand — project orientation
│   └── new-project.md            # /new-project — scaffold with docs pattern
└── templates/
    ├── CLAUDE.md                 # Workspace conventions template (installed to workspace root)
    └── settings.local.json       # Reference hook + permission config
```

## Key Design Decisions

- **No hardcoded paths** — Scripts use `Path.home()` and `Path(__file__).parent`. The installer resolves absolute paths at install time for hook registration.
- **No vault/Obsidian/Notion integration** — Stripped from the original system. Users extend via fire-and-forget subprocesses in hook_stop.py.
- **No LLM calls in hooks** — All extraction uses keyword matching and regex. Zero API cost.
- **Silent failure everywhere** — The `@_safe` decorator on all DB operations logs to stderr and returns None. Hooks never crash sessions.
- **Workspace path stored in `~/.claude-memory/workspace`** — Commands read this file to validate location. Installer creates it.
- **Three-tier permissions (allow/ask/deny)** — Kit ships with `acceptEdits` mode. Git push/merge/rebase prompt. Destructive ops blocked.

## Conventions

- `README.md` is for public/GitHub-facing docs (what it is, how to install, architecture)
- `GUIDE.md` is the comprehensive user guide (step-by-step setup, usage, permissions reference, troubleshooting)
- `templates/` contains files that get installed to user systems — edit these when changing what users receive
- `scripts/` are the actual runtime scripts — these get copied to `~/.claude-memory/scripts/`
- `commands/` are slash command definitions — these get copied to `~/.claude/commands/`

## Testing Changes

```bash
# Dry-run the installer to verify changes
./install.sh --dry-run

# Verify all scripts compile
python3 -c "import py_compile; [py_compile.compile(f'scripts/{f}', doraise=True) for f in ['memory_db.py', 'hook_session_start.py', 'hook_pre_compact.py', 'hook_stop.py', 'hook_post_tool_use.py', 'get_session_info.py']]"

# Test memory_db CRUD with a temp database
python3 -c "
import tempfile, os
os.environ['HOME'] = tempfile.mkdtemp()
import scripts.memory_db as db
conn = db.init_db()
db.create_session(conn, 'test', '/tmp/test', 'main')
assert db.get_recent_sessions(conn, 'test', 1)
conn.close()
print('All tests passed')
"
```

## Not Yet Implemented

- Public GitHub repo (local only, no remote yet)
- Subagent write guard hook (hook_subagent_write_guard.py)
- /audit and /explain commands (depend on agent definitions not included in kit)
- Auto mode documentation for Team/Enterprise users
- Upgrade/migration path between kit versions
