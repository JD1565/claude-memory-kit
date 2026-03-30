"""
Shared database module for Claude Code memory system.
WAL mode SQLite with auto-schema creation, CRUD for all tables, silent failure.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".claude-memory" / "memory.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    project_path TEXT NOT NULL,
    project_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    summary TEXT,
    work_description TEXT,
    next_steps TEXT,
    blockers TEXT,
    git_branch TEXT,
    git_commits_count INTEGER DEFAULT 0,
    compaction_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    project_name TEXT NOT NULL,
    title TEXT NOT NULL,
    decision TEXT NOT NULL,
    reasoning TEXT,
    alternatives TEXT,
    trade_offs TEXT,
    context TEXT,
    tags TEXT,
    status TEXT DEFAULT 'active',
    superseded_by INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS work_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    session_id TEXT NOT NULL,
    current_state TEXT,
    recent_changes TEXT,
    next_steps TEXT,
    blockers TEXT,
    active_files TEXT,
    git_branch TEXT,
    git_status TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    project_name TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    applies_to TEXT,
    confidence TEXT DEFAULT 'medium',
    times_applied INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_name);
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_name);
CREATE INDEX IF NOT EXISTS idx_decisions_session ON decisions(session_id);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_work_context_project ON work_context(project_name);
CREATE INDEX IF NOT EXISTS idx_learnings_project ON learnings(project_name);
CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category);
CREATE INDEX IF NOT EXISTS idx_learnings_status ON learnings(status);
"""


def derive_project_name(path: str) -> str:
    """Extract project name from a directory path."""
    if not path:
        return "unknown"
    p = Path(path).resolve()
    return p.name or "unknown"


def get_connection() -> sqlite3.Connection:
    """Get a WAL-mode connection with row_factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_schema(conn: sqlite3.Connection):
    """Create tables and indexes if they don't exist."""
    for statement in SCHEMA.split(";"):
        statement = statement.strip()
        if statement:
            try:
                conn.execute(statement)
            except sqlite3.Error:
                pass
    conn.commit()


def _safe(func):
    """Decorator for silent failure — logs to stderr, never crashes."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"memory_db.{func.__name__}: {e}", file=sys.stderr)
            return None
    return wrapper


# -- Session CRUD --

@_safe
def create_session(conn, session_id: str, project_path: str, git_branch: str = None) -> int:
    project_name = derive_project_name(project_path)
    cur = conn.execute(
        """INSERT OR IGNORE INTO sessions (session_id, project_path, project_name, started_at, git_branch)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, project_path, project_name, datetime.now().isoformat(), git_branch)
    )
    conn.commit()
    return cur.lastrowid


@_safe
def close_session(conn, session_id: str, summary: str = None, next_steps: list = None):
    conn.execute(
        """UPDATE sessions SET ended_at = ?, summary = ?, next_steps = ?
           WHERE session_id = ? AND ended_at IS NULL""",
        (datetime.now().isoformat(), summary, json.dumps(next_steps) if next_steps else None, session_id)
    )
    conn.commit()


@_safe
def update_session_data(conn, session_id: str, summary: str = None):
    """Update session summary without closing.

    Only updates if new summary is longer than existing, to avoid
    overwriting a good summary with a trivial response.
    """
    if not summary or len(summary) < 100:
        return
    existing = conn.execute(
        "SELECT summary FROM sessions WHERE session_id = ?",
        (session_id,)
    ).fetchone()
    if existing and existing["summary"] and len(existing["summary"]) >= len(summary):
        return
    conn.execute(
        "UPDATE sessions SET summary = ? WHERE session_id = ?",
        (summary, session_id)
    )
    conn.commit()


@_safe
def close_orphaned_sessions(conn, current_session_id: str = None):
    """Close sessions that were never properly ended (orphans from crashes)."""
    if current_session_id:
        conn.execute(
            """UPDATE sessions SET ended_at = ?, summary = COALESCE(summary, 'Session ended (orphan cleanup)')
               WHERE ended_at IS NULL AND session_id != ?""",
            (datetime.now().isoformat(), current_session_id)
        )
    else:
        conn.execute(
            """UPDATE sessions SET ended_at = ?, summary = COALESCE(summary, 'Session ended (orphan cleanup)')
               WHERE ended_at IS NULL""",
            (datetime.now().isoformat(),)
        )
    conn.commit()


@_safe
def increment_compaction(conn, session_id: str):
    conn.execute(
        "UPDATE sessions SET compaction_count = compaction_count + 1 WHERE session_id = ?",
        (session_id,)
    )
    conn.commit()


@_safe
def increment_git_commits(conn, session_id: str):
    conn.execute(
        "UPDATE sessions SET git_commits_count = git_commits_count + 1 WHERE session_id = ?",
        (session_id,)
    )
    conn.commit()


@_safe
def get_recent_sessions(conn, project_name: str, limit: int = 3) -> list:
    rows = conn.execute(
        """SELECT session_id, project_name, started_at, ended_at, summary,
                  work_description, next_steps, git_branch, git_commits_count, compaction_count
           FROM sessions
           WHERE project_name = ?
           ORDER BY started_at DESC
           LIMIT ?""",
        (project_name, limit)
    ).fetchall()
    return [dict(r) for r in rows]


@_safe
def get_recent_sessions_cross_project(conn, limit: int = 3) -> list:
    rows = conn.execute(
        """SELECT session_id, project_name, started_at, ended_at, summary,
                  work_description, next_steps, git_branch
           FROM sessions
           ORDER BY started_at DESC
           LIMIT ?""",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# -- Decision CRUD --

@_safe
def add_decision(conn, session_id: str, project_name: str, title: str, decision: str,
                 reasoning: str = None, alternatives: list = None, trade_offs: str = None,
                 context: str = None, tags: list = None) -> int:
    cur = conn.execute(
        """INSERT INTO decisions (session_id, project_name, title, decision, reasoning,
                                  alternatives, trade_offs, context, tags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, project_name, title, decision, reasoning,
         json.dumps(alternatives) if alternatives else None,
         trade_offs, context,
         json.dumps(tags) if tags else None)
    )
    conn.commit()
    return cur.lastrowid


@_safe
def get_active_decisions(conn, project_name: str, limit: int = 5) -> list:
    rows = conn.execute(
        """SELECT title, decision, reasoning, alternatives, trade_offs, tags, created_at
           FROM decisions
           WHERE project_name = ? AND status = 'active'
           ORDER BY created_at DESC
           LIMIT ?""",
        (project_name, limit)
    ).fetchall()
    return [dict(r) for r in rows]


@_safe
def get_cross_project_decisions(conn, limit: int = 3) -> list:
    rows = conn.execute(
        """SELECT project_name, title, decision, reasoning, tags, created_at
           FROM decisions
           WHERE status = 'active'
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# -- Work Context CRUD --

@_safe
def save_work_context(conn, project_name: str, session_id: str,
                      current_state: str = None, recent_changes: list = None,
                      next_steps: list = None, blockers: list = None,
                      active_files: list = None, git_branch: str = None,
                      git_status: str = None) -> int:
    cur = conn.execute(
        """INSERT INTO work_context (project_name, session_id, current_state, recent_changes,
                                     next_steps, blockers, active_files, git_branch, git_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_name, session_id, current_state,
         json.dumps(recent_changes) if recent_changes else None,
         json.dumps(next_steps) if next_steps else None,
         json.dumps(blockers) if blockers else None,
         json.dumps(active_files) if active_files else None,
         git_branch, git_status)
    )
    conn.commit()
    return cur.lastrowid


@_safe
def get_latest_work_context(conn, project_name: str) -> dict:
    row = conn.execute(
        """SELECT * FROM work_context
           WHERE project_name = ?
           ORDER BY created_at DESC
           LIMIT 1""",
        (project_name,)
    ).fetchone()
    return dict(row) if row else None


# -- Learnings CRUD --

@_safe
def add_learning(conn, session_id: str, project_name: str, category: str,
                 title: str, description: str, applies_to: list = None,
                 confidence: str = "medium") -> int:
    cur = conn.execute(
        """INSERT INTO learnings (session_id, project_name, category, title, description,
                                  applies_to, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, project_name, category, title, description,
         json.dumps(applies_to) if applies_to else None, confidence)
    )
    conn.commit()
    return cur.lastrowid


@_safe
def get_relevant_learnings(conn, project_name: str, limit: int = 5) -> list:
    rows = conn.execute(
        """SELECT category, title, description, applies_to, confidence, times_applied, created_at
           FROM learnings
           WHERE project_name = ? AND status = 'active'
           ORDER BY times_applied DESC, created_at DESC
           LIMIT ?""",
        (project_name, limit)
    ).fetchall()
    return [dict(r) for r in rows]


@_safe
def get_cross_project_learnings(conn, current_project: str, limit: int = 3) -> list:
    rows = conn.execute(
        """SELECT project_name, category, title, description, applies_to, confidence, created_at
           FROM learnings
           WHERE project_name != ? AND status = 'active'
           ORDER BY times_applied DESC, created_at DESC
           LIMIT ?""",
        (current_project, limit)
    ).fetchall()
    return [dict(r) for r in rows]


# -- Initialization --

def init_db() -> sqlite3.Connection:
    """Get a connection with schema ensured. Use this in hook scripts."""
    conn = get_connection()
    ensure_schema(conn)
    return conn
