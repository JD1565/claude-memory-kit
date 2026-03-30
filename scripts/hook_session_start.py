#!/usr/bin/env python3
"""
SessionStart hook: injects memory context from SQLite into Claude Code.
Reads hook input from stdin, creates session record, queries history,
returns additionalContext via stdout JSON.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import memory_db

CHAR_PER_TOKEN = 4
TOKEN_BUDGET = 2000
MAX_CONTEXT_CHARS = TOKEN_BUDGET * CHAR_PER_TOKEN  # 8000 chars


def get_git_branch(cwd: str) -> str:
    """Get current git branch for the project."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def format_session(s: dict) -> str:
    """Format a session record into a compact summary line."""
    started = s.get("started_at", "")[:16]
    summary = s.get("summary") or s.get("work_description") or "no summary"
    summary = summary[:120]
    branch = s.get("git_branch") or ""
    commits = s.get("git_commits_count", 0)
    parts = [f"  - {started}"]
    if branch:
        parts.append(f"[{branch}]")
    parts.append(f": {summary}")
    if commits:
        parts.append(f" ({commits} commits)")
    return " ".join(parts)


def format_decision(d: dict) -> str:
    """Format a decision into a compact summary."""
    lines = [f"  - **{d['title']}**: {d['decision'][:150]}"]
    if d.get("reasoning"):
        lines.append(f"    Reasoning: {d['reasoning'][:150]}")
    return "\n".join(lines)


def format_learning(l: dict) -> str:
    """Format a learning into a compact line."""
    cat = l.get("category", "tip")
    return f"  - [{cat}] **{l['title']}**: {l['description'][:150]}"


def format_work_context(wc: dict) -> str:
    """Format latest work context."""
    lines = []
    if wc.get("current_state"):
        lines.append(f"**State:** {wc['current_state'][:200]}")
    if wc.get("git_branch"):
        lines.append(f"**Branch:** {wc['git_branch']}")

    next_steps = json.loads(wc["next_steps"]) if wc.get("next_steps") else None
    if next_steps:
        lines.append("**Next steps:**")
        for step in next_steps[:5]:
            lines.append(f"  - {step}")

    blockers = json.loads(wc["blockers"]) if wc.get("blockers") else None
    if blockers:
        lines.append("**Blockers:**")
        for b in blockers[:3]:
            lines.append(f"  - {b}")

    active_files = json.loads(wc["active_files"]) if wc.get("active_files") else None
    if active_files:
        lines.append(f"**Active files:** {', '.join(active_files[:10])}")

    return "\n".join(lines)


def build_context(conn, project_name: str, project_path: str) -> str:
    """Build the additionalContext markdown string within token budget."""
    sections = []

    # Header
    sections.append(f"## Memory: {project_name}")
    sections.append(f"_Auto-injected from session history ({datetime.now().strftime('%Y-%m-%d %H:%M')})_\n")

    # Latest work context (most important — where we left off)
    wc = memory_db.get_latest_work_context(conn, project_name)
    if wc:
        sections.append("### Where You Left Off")
        sections.append(format_work_context(wc))
        sections.append("")

    # Recent sessions for this project
    sessions = memory_db.get_recent_sessions(conn, project_name, limit=3)
    if sessions:
        sections.append("### Recent Sessions")
        for s in sessions:
            sections.append(format_session(s))
        sections.append("")

    # Active decisions
    decisions = memory_db.get_active_decisions(conn, project_name, limit=5)
    if decisions:
        sections.append("### Active Decisions")
        for d in decisions:
            sections.append(format_decision(d))
        sections.append("")

    # Relevant learnings for this project
    learnings = memory_db.get_relevant_learnings(conn, project_name, limit=5)
    if learnings:
        sections.append("### Learnings")
        for l in learnings:
            sections.append(format_learning(l))
        sections.append("")

    # Cross-project learnings
    cross_learnings = memory_db.get_cross_project_learnings(conn, project_name, limit=3)
    if cross_learnings:
        sections.append("### Cross-Project Insights")
        for l in cross_learnings:
            sections.append(f"  - [{l['project_name']}] [{l['category']}] **{l['title']}**: {l['description'][:120]}")
        sections.append("")

    context = "\n".join(sections)

    # Truncate to budget
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS - 3] + "..."

    return context


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception):
        return

    session_id = input_data.get("session_id", "")
    cwd = input_data.get("cwd", os.getcwd())

    # Skip non-project sessions (home dir, no git repo)
    cwd_resolved = Path(cwd).resolve()
    if cwd_resolved == Path.home() or not (cwd_resolved / ".git").exists():
        return

    project_name = memory_db.derive_project_name(cwd)

    try:
        conn = memory_db.init_db()
    except Exception as e:
        print(f"Failed to init DB: {e}", file=sys.stderr)
        return

    try:
        memory_db.close_orphaned_sessions(conn, current_session_id=session_id)
        git_branch = get_git_branch(cwd)
        memory_db.create_session(conn, session_id, cwd, git_branch)

        context = build_context(conn, project_name, cwd)

        if context and len(context) > 100:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context
                }
            }
            print(json.dumps(output))
    except Exception as e:
        print(f"hook_session_start error: {e}", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
