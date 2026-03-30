# Changelog

All significant changes to this project are documented here.

---

_Checkpoint [2026-03-31 09:15]: Added CLAUDE.md, CHANGELOG.md, and GUIDE.md to kit project. Three-tier permissions implemented. Workspace convention with configurable directory. Notion save pending (MCP disconnected)._

---

## [2026-03-31] Session: Initial build

### Summary
Built the complete Claude Memory Kit from scratch — a portable version of the personal memory system. Extracted the core hooks, scripts, and commands from the live system, stripped personal/Obsidian-specific integrations, generalized all paths, and packaged everything with an interactive installer.

### Changes
- `install.sh` — Interactive installer with --dry-run, --uninstall, workspace prompt, hook merging, and pre-flight checks
- `scripts/memory_db.py` — Core DB module (SQLite WAL, 4 tables, @_safe decorator, full CRUD)
- `scripts/hook_session_start.py` — Context injection at session start (2000 token budget)
- `scripts/hook_pre_compact.py` — State snapshot before context compression
- `scripts/hook_stop.py` — Keyword-gated decision/learning extraction (no LLM calls)
- `scripts/hook_post_tool_use.py` — Git commit tracking (<50ms for non-commits)
- `scripts/get_session_info.py` — Session start time lookup for /save
- `commands/save.md` — End-of-session full save (CHANGELOG + memory DB + git + push)
- `commands/checkpoint.md` — Mid-session lightweight save
- `commands/understand.md` — Project orientation
- `commands/new-project.md` — Scaffold with two-layer docs pattern
- `templates/CLAUDE.md` — Workspace conventions template with two-layer docs explanation
- `templates/settings.local.json` — Reference config with three-tier permissions (allow/ask/deny)
- `README.md` — Full architecture docs, workspace convention, permissions guide, FAQ
- `GUIDE.md` — Complete user guide (setup, usage, capabilities, permissions reference, troubleshooting)
- `.gitignore` — Standard Python + DB exclusions

### Key Decisions
- Workspace directory convention (default ~/Claude/) instead of hardcoded ~/Dev/
- acceptEdits as default permission mode (works on all plans)
- Three-tier permissions: allow common commands, ask for git push/merge/rebase, deny destructive ops
- Stripped vault/Obsidian/Notion integration (users extend via hook_stop.py)
- No LLM calls in any hook (all regex/keyword extraction)

### Git Commits
- (initial commit pending)

### Next Steps
- [ ] Create GitHub remote and push
- [ ] Add subagent write guard hook
- [ ] Test full install flow on a clean machine
- [ ] Add /audit and /explain commands (requires bundling agent definitions)
- [ ] Document auto mode upgrade path for Team/Enterprise users

---
