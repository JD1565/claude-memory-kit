# Claude Memory Kit — Complete Guide

A persistent memory system for Claude Code. Claude remembers where you left off, what decisions you made, and what you learned — across sessions and across projects.

---

## Prerequisites

Before installing, you need:

- **Claude Code CLI** — Install from https://docs.anthropic.com/en/docs/claude-code
- **Python 3.9+** — Check with `python3 --version`
- **Git** — Check with `git --version`
- **GitHub CLI** (optional) — For `/new-project` to create remotes. Install from https://cli.github.com

---

## Installation

### Step 1: Clone the kit

```bash
git clone https://github.com/YOUR_USERNAME/claude-memory-kit.git
cd claude-memory-kit
```

### Step 2: Run the installer

```bash
./install.sh
```

The installer will:

1. **Check prerequisites** — Verifies Python 3.9+ and git are installed
2. **Ask for your workspace directory** — Where all your projects will live (default: `~/Claude/`). This can be any path. Choose `~/Dev/` if your projects are code-only, or `~/Claude/` if you'll also use it for research, writing, and planning
3. **Install 6 Python scripts** to `~/.claude-memory/scripts/`
4. **Install 4 slash commands** to `~/.claude/commands/`
5. **Register 4 hooks** in `~/.claude/settings.local.json` (merges with existing config if present)
6. **Create your workspace** directory with a `CLAUDE.md` conventions file
7. **Save the workspace path** to `~/.claude-memory/workspace`

### Step 3: Verify

Start a new Claude Code session inside your workspace:

```bash
cd ~/Claude   # or whatever you chose
claude
```

You should see no errors. The memory database (`~/.claude-memory/memory.db`) is created automatically on first session.

### Other installer options

```bash
./install.sh --dry-run     # Preview what would happen without making changes
./install.sh --uninstall   # Remove installed files (preserves your memory.db)
```

---

## What Gets Installed

### Files on your system

```
~/Claude/                           # Your workspace
  CLAUDE.md                         # Conventions file (Claude reads this automatically)

~/.claude-memory/
  memory.db                         # SQLite database (created on first session)
  workspace                         # Your workspace path (one line)
  scripts/
    memory_db.py                    # Core database module
    hook_session_start.py           # Injects context at session start
    hook_pre_compact.py             # Saves state before context compression
    hook_stop.py                    # Extracts decisions and learnings
    hook_post_tool_use.py           # Tracks git commits
    get_session_info.py             # Helper for /save command

~/.claude/
  settings.local.json               # Hook registrations + permissions
  commands/
    save.md                         # /save command
    checkpoint.md                   # /checkpoint command
    understand.md                   # /understand command
    new-project.md                  # /new-project command
```

### The database

Four tables in `~/.claude-memory/memory.db`:

| Table | What it stores |
|-------|---------------|
| **sessions** | Session lifecycle — start/end times, project, branch, commit count, compaction count |
| **decisions** | Architecture decisions — title, reasoning, alternatives, trade-offs |
| **work_context** | State snapshots — what you're working on, next steps, blockers, active files |
| **learnings** | Reusable insights — gotchas, workarounds, patterns, with confidence scores |

You can query it directly:

```bash
sqlite3 ~/.claude-memory/memory.db "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 5;"
```

---

## How to Use It

### Starting a new project

```bash
cd ~/Claude
claude
```

Then type:

```
/new-project my-project-name
```

Claude will:
- Create `~/Claude/my-project-name/` with git init
- Ask you what the project does
- Generate README.md, CHANGELOG.md, and .gitignore
- Optionally create a GitHub remote
- Save a context snapshot to the memory DB

### Orienting on an existing project

```bash
cd ~/Claude/my-project
claude
```

Then type:

```
/understand
```

Claude reads the project's README, CHANGELOG, and CLAUDE.md, presents a concise overview, and saves a context snapshot so future sessions know where things stand.

### Working on a project

Just work normally. The memory system runs silently in the background:

- **Every time Claude responds**, the Stop hook checks for decisions, learnings, and next steps using keyword matching. If it finds any, it saves them to the database. If not, it exits in under 50ms.
- **Every time you make a git commit**, the PostToolUse hook increments the commit counter on your session.
- **If the context window gets compressed**, the PreCompact hook saves a full state snapshot first so nothing is lost.

You don't need to do anything — it's all automatic.

### Mid-session checkpoint

When you want to save progress without ending the session:

```
/checkpoint Added the authentication module
```

This appends a one-line breadcrumb to CHANGELOG.md and saves a work_context snapshot to the database. No git commit, no push.

### Ending a session

```
/save Built the authentication module with JWT tokens
```

This does everything in one command:

1. Reads git status and queries the memory DB for session context
2. Writes a structured entry to CHANGELOG.md (matching the existing format)
3. Removes any checkpoint entries from this session (they're superseded)
4. Saves final state and closes the session in the memory DB
5. Scans for secrets (`.env`, `*.pem`, `*.key`) before staging
6. Stages files explicitly (not `git add -A`)
7. Commits with a summary message
8. Pulls with rebase then pushes (safe for multi-machine use)
9. Reports a summary

### Starting the next session

```bash
cd ~/Claude/my-project
claude
```

The SessionStart hook automatically injects context from the previous session:

- **Where you left off** — last work_context snapshot (state, next steps, blockers, active files)
- **Recent sessions** — last 3 sessions for this project (date, branch, summary, commits)
- **Active decisions** — up to 5 architecture decisions with reasoning
- **Learnings** — up to 5 project-specific gotchas/patterns
- **Cross-project insights** — up to 3 learnings from other projects

This is capped at 2000 tokens (~8000 chars) to avoid bloating the context window.

---

## Capabilities

### What the system captures automatically

| What | How | When |
|------|-----|------|
| **Session history** | Creates/closes session records with timing, branch, commit count | Start and end of every session |
| **Decisions** | Regex extraction from responses containing "decided", "chose", "trade-off", etc. | After each Claude response (keyword-gated) |
| **Learnings** | Regex extraction from responses containing "learned", "gotcha", "turns out", etc. | After each Claude response (keyword-gated) |
| **Next steps** | Regex extraction from bullet lists after "next step", "todo", "remaining" headers | After each Claude response (keyword-gated) |
| **Work context** | Full state snapshot (current state, active files, git status, next steps, blockers) | Before every context compression |
| **Git commits** | Increment counter on session record | After every `git commit` command |
| **Session summary** | Last substantive assistant message (>100 chars, longest wins) | Updated on every response |
| **Orphan cleanup** | Closes sessions that were never properly ended (from crashes) | At start of every new session |

### What carries between projects

Learnings are not siloed. When you discover a gotcha in Project A, it appears as a "Cross-Project Insight" when you start a session in Project B. This is especially useful for patterns that apply across multiple codebases (e.g., "WAL mode prevents SQLite locking issues").

### What it does NOT do

- No cloud sync — the database is local to each machine
- No UI or dashboard — query with `sqlite3` directly
- No LLM calls for extraction — everything uses regex and keywords (zero API cost)
- No integration with Obsidian, Notion, or other tools (those are extensions you can add)
- No team/multi-user features — this is a single-user system

---

## The Two-Layer Documentation Pattern

Every project gets two documentation files with distinct purposes:

### README.md — "What this project IS"

- Current status and phase
- Tech stack
- Quick start instructions
- Architecture overview
- Max 5 next actions
- **Rewritten** as the project evolves — not append-only

### CHANGELOG.md — "What HAPPENED"

- Complete session-by-session history
- Each `/save` adds a structured entry (summary, changes, commits, next steps)
- Each `/checkpoint` adds a lightweight breadcrumb
- **Append-only** — never edit old entries

This separation prevents documentation rot. README stays concise because it holds no history. CHANGELOG stays useful because it's never mixed with current-state descriptions.

---

## Permissions Reference

The kit configures Claude Code with `acceptEdits` mode and a three-tier permission system. File edits are auto-approved. Bash commands are controlled by the allow/ask/deny lists below.

Rules are evaluated in order: **deny > ask > allow**. The first match wins.

### Deny — Blocked entirely

| Rule | What it prevents |
|------|-----------------|
| `Bash(rm -rf /)` | Deleting the entire filesystem |
| `Bash(rm -rf ~*)` | Deleting the home directory |
| `Bash(dd *)` | Raw disk writes that can destroy partitions |
| `Bash(mkfs *)` | Formatting filesystems |
| `Bash(git push --force *)` | Overwriting remote git history |
| `Bash(git reset --hard *)` | Discarding all uncommitted work |

### Ask — Prompts for confirmation

| Rule | Why it prompts |
|------|---------------|
| `Bash(git push *)` | Pushes are visible to others and affect shared state |
| `Bash(git merge *)` | Merges can introduce conflicts and change branch state |
| `Bash(git rebase *)` | Rewrites commit history |
| `Bash(git tag *)` | Publishes version markers to remotes |
| `Bash(sudo *)` | Runs commands with root privileges |
| `Bash(systemctl *)` | Manages system services (start, stop, enable, disable) |

### Allow — Auto-approved, no prompt

**Git (safe operations):**

| Rule | What it allows |
|------|---------------|
| `Bash(git status)` | Check working tree state |
| `Bash(git diff *)` | View file differences |
| `Bash(git log *)` | View commit history |
| `Bash(git add *)` | Stage files for commit |
| `Bash(git commit *)` | Create commits |
| `Bash(git checkout *)` | Switch branches or restore files |
| `Bash(git branch *)` | List, create, or delete branches |
| `Bash(git stash *)` | Temporarily shelve changes |
| `Bash(git fetch *)` | Download remote refs without merging |
| `Bash(git remote *)` | View or manage remotes |
| `Bash(git rev-parse *)` | Resolve git references (used internally) |

**Language tools:**

| Rule | What it allows |
|------|---------------|
| `Bash(python3 *)` | Run Python scripts and commands |
| `Bash(python *)` | Run Python (alternate command) |
| `Bash(pip *)` | Install/manage Python packages |
| `Bash(npm *)` | Node.js package manager |
| `Bash(npx *)` | Run npm packages without installing |
| `Bash(node *)` | Run Node.js scripts |
| `Bash(cargo *)` | Rust package manager and build tool |
| `Bash(make *)` | Run Makefiles |

**File operations:**

| Rule | What it allows |
|------|---------------|
| `Bash(ls *)` | List directory contents |
| `Bash(cat *)` | Display file contents |
| `Bash(head *)` | Display first lines of a file |
| `Bash(tail *)` | Display last lines of a file |
| `Bash(mkdir *)` | Create directories |
| `Bash(cp *)` | Copy files |
| `Bash(mv *)` | Move or rename files |
| `Bash(rm *)` | Delete files (not `rm -rf /` or `rm -rf ~*` — those are denied) |
| `Bash(chmod *)` | Change file permissions |
| `Bash(find *)` | Search for files |
| `Bash(wc *)` | Count lines, words, characters |
| `Bash(echo *)` | Print text |
| `Bash(grep *)` | Search file contents |
| `Bash(sort *)` | Sort lines |
| `Bash(uniq *)` | Filter duplicate lines |
| `Bash(diff *)` | Compare files |
| `Bash(touch *)` | Create empty files or update timestamps |
| `Bash(tree *)` | Display directory tree |
| `Bash(tar *)` | Archive and compress files |

**Network:**

| Rule | What it allows |
|------|---------------|
| `Bash(curl *)` | Make HTTP requests |
| `Bash(wget *)` | Download files |

**Utilities:**

| Rule | What it allows |
|------|---------------|
| `Bash(* --version)` | Check version of any tool |
| `Bash(* --help)` | View help for any tool |
| `Bash(which *)` | Find location of a command |

**Claude Code tools:**

| Rule | What it allows |
|------|---------------|
| `Agent` | Launch subagent tasks (research, exploration, etc.) |
| `WebSearch` | Search the web for information |
| `WebFetch` | Fetch content from URLs |

### Permission modes

You can change mode mid-session with `Shift+Tab`:

| Mode | File edits | Bash commands | When to use |
|------|-----------|--------------|------------|
| `default` | Prompts | Prompts | Maximum oversight |
| **`acceptEdits`** | **Auto** | **Allow/ask/deny lists** | **Daily driver (kit default)** |
| `plan` | Blocked | Blocked | Read-only exploration |
| `auto` | Classifier auto-approves | Classifier auto-approves | Team/Enterprise/API plans only |
| `bypassPermissions` | All auto | All auto | Containers/VMs only |

### Customizing

Edit `~/.claude/settings.local.json` to add your own rules:

```json
{
  "permissions": {
    "allow": ["Bash(your-safe-command *)"],
    "ask": ["Bash(your-risky-command *)"],
    "deny": ["Bash(your-dangerous-command *)"]
  }
}
```

---

## Hooks Reference

Four hooks run automatically. All use a silent failure decorator — they never crash or block your session. If anything goes wrong, they log to stderr and continue.

### SessionStart

**When:** New Claude Code session begins
**Timeout:** 8 seconds
**What it does:**
1. Closes any orphaned sessions from previous crashes
2. Creates a new session record in the database
3. Queries the database for previous context (work_context, sessions, decisions, learnings)
4. Injects up to 2000 tokens of context into the conversation via `additionalContext`
**Skips:** Non-git directories and the home directory (to avoid polluting the DB)

### Stop

**When:** After every Claude response
**Timeout:** 5 seconds
**What it does:**
1. Updates the session summary (keeps the DB fresh)
2. Checks for significance keywords in the response
3. If keywords found: extracts decisions (max 3), learnings (max 3), and next steps (max 10) via regex
4. Saves extracted data to the database
**Performance:** Exits in <50ms if no keywords match. No LLM calls.

**Keywords that trigger extraction:**
- Decisions: "decided", "chose", "trade-off", "instead of", "rather than", ...
- Learnings: "learned", "gotcha", "turns out", "workaround", "tip", ...
- Context: "next step", "blocker", "todo", "need to", "remaining", ...

### PreCompact

**When:** Before Claude Code compresses the context window
**Timeout:** 5 seconds
**What it does:**
1. Parses the last 50 lines of the session transcript
2. Extracts: current state, active files, next steps
3. Saves a full work_context snapshot to the database
4. Increments the compaction counter on the session

### PostToolUse

**When:** After any Bash command
**Timeout:** 3 seconds
**What it does:**
1. Quick exit if the command doesn't contain "git commit" (<50ms)
2. If it's a git commit: increments the commit counter on the session record

---

## Troubleshooting

### Hooks aren't firing

Check that the hooks are registered:
```bash
cat ~/.claude/settings.local.json | python3 -m json.tool | grep hook_session_start
```

If nothing shows, re-run `./install.sh`.

### No context injected at session start

The SessionStart hook skips non-git directories. Make sure you're inside a git repository:
```bash
git rev-parse --git-dir
```

### Database is empty

The database is created on first session and populated as you work. Run `/understand` in a project to create the first work_context entry.

### Check hook errors

Hook errors go to stderr, which isn't normally visible. Check the hook manually:
```bash
echo '{"session_id":"test","cwd":"'$PWD'"}' | python3 ~/.claude-memory/scripts/hook_session_start.py
```

### Reset the database

```bash
rm ~/.claude-memory/memory.db
# Recreated automatically on next session
```

---

## Uninstalling

```bash
cd claude-memory-kit
./install.sh --uninstall
```

This removes scripts and commands but preserves:
- `~/.claude-memory/memory.db` (your session history)
- `~/.claude/settings.local.json` (review and remove hook entries manually)
