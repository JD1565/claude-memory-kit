#!/usr/bin/env python3
"""
Get current session info for the active project.

Used by /save to determine session start time for git log --since.
Falls back to "4 hours ago" if no session found.

Usage: python3 get_session_info.py [project_path]
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memory_db


def get_session_info(project_path: str = None) -> dict:
    project_path = project_path or os.getcwd()
    project_name = memory_db.derive_project_name(project_path)

    fallback = {
        "session_id": "",
        "started_at": (datetime.now() - timedelta(hours=4)).isoformat(),
        "git_branch": "",
        "git_commits_count": 0,
        "fallback": True,
    }

    try:
        conn = memory_db.init_db()
        row = conn.execute(
            """SELECT session_id, started_at, git_branch, git_commits_count
               FROM sessions
               WHERE project_name = ? AND ended_at IS NULL
               ORDER BY started_at DESC
               LIMIT 1""",
            (project_name,),
        ).fetchone()
        conn.close()

        if row:
            return {
                "session_id": row["session_id"],
                "started_at": row["started_at"],
                "git_branch": row["git_branch"] or "",
                "git_commits_count": row["git_commits_count"] or 0,
                "fallback": False,
            }
        return fallback
    except Exception:
        return fallback


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    info = get_session_info(path)
    print(json.dumps(info, indent=2))
