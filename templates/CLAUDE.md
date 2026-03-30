# Workspace Conventions

## Workspace Structure

All projects live under `~/Claude/` (or whichever workspace you chose during install). Each project is its own git repository with standardized documentation.

```
~/Claude/                     # Workspace root (this CLAUDE.md lives here)
├── project-alpha/            # Each project is a separate git repo
│   ├── README.md             # Source of truth: what the project IS
│   ├── CHANGELOG.md          # Session history: what HAPPENED
│   ├── CLAUDE.md             # Project-specific conventions (optional)
│   └── ...
├── project-beta/
│   ├── README.md
│   ├── CHANGELOG.md
│   └── ...
└── CLAUDE.md                 # This file: workspace-wide conventions
```

### The Two-Layer Documentation Pattern

Every project uses two documentation files with distinct purposes:

**README.md** — "What this project IS right now"
- Current state, status, tech stack
- Quick start instructions
- Architecture overview
- Max 5 next actions
- No historical data — this file is rewritten, not appended

**CHANGELOG.md** — "What HAPPENED across sessions"
- Append-only session history
- Each `/save` adds a structured entry
- Each `/checkpoint` adds a lightweight breadcrumb
- Never edit old entries — only append new ones

The separation prevents docs from going stale. README stays concise because history lives in CHANGELOG. CHANGELOG stays useful because it's never mixed with current-state content.

### Creating New Projects

Use `/new-project [name]` to scaffold a project with the correct structure. This creates the directory, initializes git, generates both doc files, and optionally creates a GitHub remote.

## Memory System

Persistent memory lives in `~/.claude-memory/memory.db` (SQLite, WAL mode).

### Database Schema
Four tables track cross-session context:
- **sessions** — Session lifecycle (start/end times, project, git branch, compaction count)
- **decisions** — Architecture decisions with reasoning, alternatives, and trade-offs
- **work_context** — Snapshots of project state (current state, next steps, blockers, active files)
- **learnings** — Reusable insights with confidence scores and application counts

All queries support both project-specific and cross-project lookups (insights carry between projects).

### Hooks (`~/.claude/settings.local.json`)
Four hooks auto-capture context without manual intervention:
- **SessionStart** — Injects previous context from memory DB (budget: 2000 tokens / 8000 chars max), closes orphaned sessions from crashes, loads recent sessions + decisions + learnings + cross-project insights
- **PreCompact** — Saves work context snapshot before context window compression (parses last 50 lines of transcript for state, active files, next steps)
- **Stop** — Heuristic extraction of decisions and learnings from responses using keyword/regex matching (no LLM calls). Skips short or insignificant responses. Max 3 decisions/learnings per response
- **PostToolUse** (Bash) — Tracks git commits, increments commit counter on session record

Scripts live in `~/.claude-memory/scripts/`. All hooks use a silent failure decorator — they never crash or block the session.

## Workflow Commands
- `/new-project [name]` — Scaffold a new project with README, CHANGELOG, .gitignore, git init
- `/understand` — Orient on project (reads README + CHANGELOG, saves context snapshot)
- `/checkpoint [note]` — Mid-session progress save (CHANGELOG note + memory DB, no git commit)
- `/save [summary]` — End session: CHANGELOG entry + memory DB + git commit + push

## Git Conventions
- Commit messages: concise, focus on "why" not "what"
- Each project manages its own git repo (the workspace root is not a git repo)
- `/save` handles staging, committing, and pushing at end of session
- Multi-machine safety: pull with rebase before push, stop on conflicts
- Secret detection: `/save` scans for `.env`, `*.pem`, `*.key` patterns before staging
- Explicit file staging (not `git add -A`) to avoid accidentally committing secrets or binaries
- Never force-push or amend published commits without explicit request
