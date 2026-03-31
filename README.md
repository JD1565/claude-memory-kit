# Claude Memory Kit

A persistent memory system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that gives Claude context across sessions. When you start a new conversation, Claude already knows where you left off, what decisions you made, and what you learned.

## The Problem

Claude Code starts every session with a blank slate. You have to re-explain your project state, remind it of past decisions, and re-orient it on what you were doing. This gets worse as projects grow and sessions accumulate.

## The Solution

Four lightweight hooks that fire automatically during your Claude Code sessions:

| Hook | When it fires | What it does |
|------|--------------|-------------|
| **SessionStart** | New session begins | Injects last session's context (where you left off, recent decisions, learnings) |
| **PreCompact** | Before context compression | Saves a state snapshot so nothing is lost when the context window shrinks |
| **Stop** | After each Claude response | Extracts decisions, learnings, and next steps using keyword/regex heuristics |
| **PostToolUse** | After git commits | Tracks commit count per session |
| **PreToolUse** | Before file writes | Blocks subagent writes outside allowed directories |

Everything is stored in a local SQLite database (`~/.claude-memory/memory.db`). No LLM calls, no external services, no API costs. The hooks use a silent failure decorator so they never crash or block your session.

## What You Get

- **Session continuity** — Claude picks up exactly where the last session ended
- **Decision tracking** — Architecture choices are captured with reasoning and trade-offs
- **Cross-project learning** — Insights from one project surface in others
- **Session history** — CHANGELOG.md becomes your project diary via `/save`
- **Crash recovery** — Orphaned sessions from crashes are automatically cleaned up

## Quick Start

```bash
git clone https://github.com/JD1565/claude-memory-kit.git
cd claude-memory-kit
./install.sh
```

The installer will:
1. Ask you to choose a **workspace directory** (default: `~/Claude/`)
2. Copy 7 Python scripts to `~/.claude-memory/scripts/`
3. Install 4 slash commands to `~/.claude/commands/`
4. Register hooks in `~/.claude/settings.local.json`
5. Create the workspace directory with a `CLAUDE.md` conventions file

Then start Claude Code inside your workspace and use `/new-project` to create your first project.

### Requirements

- Python 3.9+
- Git
- Claude Code CLI

## Workspace Convention

The kit expects all your projects to live under a single workspace directory. During installation you'll choose where this is — the default is `~/Claude/`.

```
~/Claude/                       # Your workspace root
├── CLAUDE.md                   # Workspace-wide conventions (installed automatically)
├── my-api/                     # Each project is its own git repo
│   ├── README.md               # What the project IS (current state)
│   ├── CHANGELOG.md            # What HAPPENED (session history)
│   └── ...
├── research-notes/
│   ├── README.md
│   ├── CHANGELOG.md
│   └── ...
└── ...
```

**Why a dedicated workspace?**
- Gives the memory system a consistent root to anchor against
- `/save` and `/checkpoint` validate you're working inside the workspace
- `/new-project` creates projects in the right place automatically
- The workspace `CLAUDE.md` gives Claude conventions that apply to all projects
- Projects don't have to be code — research, writing, planning all work the same way

### Parent-Child CLAUDE.md Inheritance

Claude Code natively walks up the directory tree and loads every `CLAUDE.md` it finds. The kit uses this to create a two-level hierarchy:

- **Workspace `CLAUDE.md`** (parent) — conventions that apply to all projects, plus a project registry table so Claude always knows what exists in the workspace
- **Project `CLAUDE.md`** (child, optional) — project-specific conventions, architecture decisions, phase tracking

When you start a session in `~/Claude/my-api/`, Claude loads both files. This means Claude is aware of the broader workspace context — sibling projects, shared conventions — without you having to explain it. The `/new-project` command automatically registers each new project in the parent's registry table.

**Why not `~/Dev/`?** You can use `~/Dev/` if you prefer — the installer lets you choose any path. `~/Claude/` is the default because the workspace isn't limited to software development.

### The Two-Layer Documentation Pattern

Every project created with `/new-project` gets two files:

| File | Purpose | How it changes |
|------|---------|---------------|
| **README.md** | What the project IS right now — status, stack, quick start, next actions | Rewritten as the project evolves |
| **CHANGELOG.md** | What HAPPENED — complete session-by-session history | Append-only, never edit old entries |

This separation keeps docs from going stale. README stays concise because it holds no history. CHANGELOG stays useful because it's never mixed with current-state content.

## Commands

### `/save [summary]`

End-of-session save. Does everything in one command:

1. Reads git status and session history from the memory DB
2. Writes a structured CHANGELOG.md entry
3. Saves final state to the memory DB and closes the session
4. Stages files with secret scanning (warns on `.env`, `*.pem`, `*.key`)
5. Commits with a summary message
6. Pulls with rebase then pushes (safe for multi-machine workflows)

### `/checkpoint [note]`

Mid-session lightweight save. Appends an italic one-liner to CHANGELOG.md and saves a work_context snapshot to the DB. No git commit, no push — just a breadcrumb.

### `/understand`

Orient on a project. Reads README.md, CHANGELOG.md, CLAUDE.md, and package manifest, then presents a concise overview and saves a context snapshot.

### `/new-project [name]`

Scaffold a new project with the standard docs pattern:

1. Creates a project directory with `git init`
2. Generates README.md (source of truth for current state)
3. Generates CHANGELOG.md (append-only session history)
4. Creates .gitignore adapted to the tech stack
5. Makes an initial commit
6. Optionally creates a private GitHub remote via `gh`
7. Saves a context snapshot to the memory DB

## Architecture

### Database Schema

```
~/.claude-memory/memory.db (SQLite, WAL mode)
├── sessions      — Session lifecycle (start/end, project, branch, commit count)
├── decisions     — Architecture decisions with reasoning and trade-offs
├── work_context  — State snapshots (current state, next steps, blockers, active files)
└── learnings     — Reusable insights with confidence scores
```

### How Context Flows

```
Session N (ending)                    Session N+1 (starting)
─────────────────                     ───────────────────────

  Claude response                       SessionStart hook
       │                                      │
  Stop hook fires                        Queries memory DB
       │                                      │
  Keyword detection                    ┌──────┴──────┐
       │                               │             │
  ┌────┴─────┐                    Latest work    Recent sessions
  │          │                    context         (last 3)
Decisions  Learnings                  │             │
  │          │                    Active         Cross-project
  └────┬─────┘                    decisions      learnings
       │                               │             │
  Saved to SQLite                 └──────┬──────┘
       │                                 │
  PreCompact hook ──────►        Injected as
  (state snapshot                additionalContext
   before compression)           (max 2000 tokens)
```

### Hook Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│ SessionStart                                             │
│  1. Close orphaned sessions from crashes                 │
│  2. Create new session record                            │
│  3. Build context: work_context + sessions + decisions   │
│  4. Inject via stdout JSON (additionalContext)           │
│  Budget: 2000 tokens (8000 chars)                        │
│  Skip: non-git directories, home directory               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Stop (fires after every Claude response)                 │
│  1. Update session summary (keeps DB fresh)              │
│  2. Check significance keywords                          │
│     - Decision: "decided", "chose", "trade-off", ...     │
│     - Learning: "learned", "gotcha", "turns out", ...    │
│     - Context:  "next step", "blocker", "todo", ...      │
│  3. Extract via regex (max 3 decisions, 3 learnings)     │
│  4. Save to SQLite                                       │
│  Exit fast (<50ms) if no keywords match                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PreCompact (fires before context window compression)     │
│  1. Parse last 50 lines of transcript                    │
│  2. Extract: state, active files, next steps             │
│  3. Save work_context snapshot                           │
│  4. Increment compaction count                           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PostToolUse (fires after Bash commands)                   │
│  1. Quick exit if not "git commit" (<50ms)               │
│  2. Increment git_commits_count on session               │
└─────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Silent failure** — All DB operations use a `@_safe` decorator. If anything goes wrong, it logs to stderr and continues. Hooks never crash your session.

2. **Keyword-gated extraction** — Decisions and learnings are only extracted when specific keywords appear in responses. This prevents DB pollution from trivial responses.

3. **No LLM calls** — All extraction uses regex and keyword matching. Zero additional API cost.

4. **Token budget** — Context injection is capped at 2000 tokens (~8000 chars) to avoid bloating the context window.

5. **Multi-project support** — Learnings carry between projects. What you discover in project A surfaces as "cross-project insights" when working on project B.

## File Structure

```
claude-memory-kit/
├── install.sh                    # Interactive installer
├── README.md                     # This file
├── scripts/
│   ├── memory_db.py              # Core DB module (schema, CRUD, @_safe)
│   ├── hook_session_start.py     # SessionStart — context injection
│   ├── hook_pre_compact.py       # PreCompact — state snapshot
│   ├── hook_stop.py              # Stop — decision/learning extraction
│   ├── hook_post_tool_use.py     # PostToolUse — git commit tracking
│   ├── hook_subagent_write_guard.py # PreToolUse — subagent write restriction
│   └── get_session_info.py       # Helper for /save command
├── commands/
│   ├── save.md                   # /save slash command
│   ├── checkpoint.md             # /checkpoint slash command
│   ├── understand.md             # /understand slash command
│   └── new-project.md            # /new-project scaffold command
└── templates/
    ├── CLAUDE.md                 # Global conventions template
    └── settings.local.json       # Reference hook configuration
```

After installation:

```
~/Claude/                           # Workspace (you choose the path)
└── CLAUDE.md                       # Workspace conventions (installed by kit)

~/.claude-memory/
├── memory.db                       # SQLite database (created on first session)
├── workspace                       # Workspace path (one line, e.g. /home/you/Claude)
└── scripts/                        # Hook scripts (copied by installer)

~/.claude/
├── settings.local.json             # Hook registrations (merged by installer)
└── commands/                       # Slash commands (copied by installer)
    ├── save.md
    ├── checkpoint.md
    ├── understand.md
    └── new-project.md
```

## Customization

### Adjusting the context budget

In `hook_session_start.py`, change `TOKEN_BUDGET` to inject more or less context:

```python
TOKEN_BUDGET = 2000   # Default: ~8000 chars
TOKEN_BUDGET = 4000   # Double: ~16000 chars (uses more context window)
TOKEN_BUDGET = 1000   # Half: ~4000 chars (minimal footprint)
```

### Adding extraction keywords

In `hook_stop.py`, add keywords to the sets to capture more patterns:

```python
DECISION_KEYWORDS = {
    "decided", "chose", ...,
    "your_keyword_here",  # Add custom keywords
}
```

### Extending with vault/notes integration

The Stop hook has a clean extension point. After the main extraction logic, you can spawn fire-and-forget subprocesses to sync to external systems (Obsidian, Notion, etc.):

```python
# In hook_stop.py, after the keyword-gated extraction:
def spawn_my_sync(session_id, project_name, cwd):
    subprocess.Popen(
        [sys.executable, "/path/to/my_sync.py", ...],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
```

## Permissions and Reducing Prompts

Claude Code prompts you for approval before running commands or editing files. The kit ships with a permission configuration that minimizes these prompts while keeping destructive operations gated.

### Permission Modes

Claude Code has several permission modes. You can cycle through them with `Shift+Tab` during a session, or set a default in settings.

| Mode | File edits | Bash commands | Best for |
|------|-----------|--------------|---------|
| `default` | Prompts | Prompts | Getting started, maximum oversight |
| `acceptEdits` | Auto-approve | Prompts (unless in allow list) | **Daily driver (kit default)** |
| `plan` | Blocked | Blocked | Read-only exploration and planning |
| `auto` | Classifier approves | Classifier approves | Long-running tasks (Team/Enterprise/API plans only) |
| `bypassPermissions` | All auto | All auto | Isolated containers/VMs only |

The kit defaults to `acceptEdits` because it works on all plans and gives the best balance — file edits happen without interruption, and Bash commands are controlled by the allow/ask/deny lists.

### Three-Tier Permission Rules

The kit's `settings.local.json` uses three tiers. Rules are evaluated in order: **deny > ask > allow**.

**Allow** — Auto-approved, no prompt:
- Safe git operations (status, diff, log, add, commit, checkout, branch, stash, fetch)
- Language tools (python, node, npm, cargo, make)
- File operations (ls, cat, mkdir, cp, mv, find, grep, etc.)
- Web tools (curl, wget, WebSearch, WebFetch)
- Agent subagents

**Ask** — Prompts for confirmation:
- `git push` — pushes to remotes are visible to others
- `git merge`, `git rebase` — can rewrite history
- `git tag` — publishes version markers
- `sudo` / `systemctl` — system-level changes

**Deny** — Blocked entirely:
- `rm -rf /` and `rm -rf ~*` — catastrophic deletion
- `dd`, `mkfs` — disk-level operations
- `git push --force` — overwrites remote history
- `git reset --hard` — discards uncommitted work

### Customizing Permissions

Edit `~/.claude/settings.local.json` to adjust:

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(your-command *)"
    ],
    "ask": [
      "Bash(risky-command *)"
    ],
    "deny": [
      "Bash(dangerous-command *)"
    ]
  }
}
```

**Syntax notes:**
- `Bash(npm run *)` — matches `npm run build`, `npm run test`, etc.
- `Bash(ls *)` (with space before `*`) — matches `ls -la` but NOT `lsof`
- `Bash(ls*)` (no space) — matches both `ls -la` and `lsof`
- Deny rules always win over allow rules, regardless of where they're defined

### Auto Mode (Team/Enterprise/API Plans)

If you're on a Team, Enterprise, or API plan with Sonnet 4.6 or Opus 4.6, you can enable `auto` mode — a background classifier model approves actions automatically without prompting:

```bash
claude --enable-auto-mode
# Then cycle to auto mode with Shift+Tab
```

Auto mode is not yet available on Pro or free plans. No timeline has been announced.

### Permission File Precedence

Settings are loaded in priority order (highest wins):

1. **Managed** — `/etc/claude-code/managed-settings.json` (org-wide, cannot override)
2. **CLI flags** — `--permission-mode`, `--allowedTools` (current session)
3. **Local project** — `.claude/settings.local.json` (you, this project, gitignored)
4. **Shared project** — `.claude/settings.json` (committed, team-wide)
5. **User** — `~/.claude/settings.json` (you, all projects)

A deny at any level cannot be overridden by a lower level — except that local project settings can override shared project settings (this is the intended escape hatch for personal overrides).

## FAQ

**Does this slow down Claude Code?**
No. Hooks exit in <50ms for non-significant events. The heaviest hook (SessionStart) has an 8-second timeout but typically completes in <500ms. All hooks use a silent failure decorator — they never hang or crash.

**How much disk space does the database use?**
Minimal. After 20+ sessions across multiple projects, the database is ~350KB. SQLite WAL mode keeps it efficient.

**Can I inspect the database?**
Yes. It's standard SQLite:
```bash
sqlite3 ~/.claude-memory/memory.db
.tables
SELECT * FROM sessions ORDER BY started_at DESC LIMIT 5;
SELECT * FROM decisions WHERE status = 'active';
SELECT * FROM learnings ORDER BY times_applied DESC;
```

**What if I use Claude Code on multiple machines?**
The database is local to each machine. The `/save` command uses `git pull --rebase` before pushing to handle divergence safely. Session history stays on the machine where the session ran, but your CHANGELOG.md syncs via git.

**Can I reset the database?**
```bash
rm ~/.claude-memory/memory.db
# It will be recreated on the next session
```

**How do I uninstall?**
```bash
cd claude-memory-kit
./install.sh --uninstall
```
This removes scripts and commands but preserves your `memory.db` and `settings.local.json` (review the settings file to remove hook entries manually).

## License

MIT
