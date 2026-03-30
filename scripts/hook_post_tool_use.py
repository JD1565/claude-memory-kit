#!/usr/bin/env python3
"""
PostToolUse hook: tracks git commits.
Fires on Bash tool use, checks for "git commit" in input.
Exits in <50ms for non-git commands.
"""

import json
import sys
from pathlib import Path


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception):
        return

    # Quick exit for non-Bash or non-git-commit commands
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return

    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return

    # Only reach here for git commit commands — worth the DB overhead
    session_id = input_data.get("session_id", "")
    if not session_id:
        return

    sys.path.insert(0, str(Path(__file__).parent))
    import memory_db

    try:
        conn = memory_db.init_db()
        memory_db.increment_git_commits(conn, session_id)
        conn.close()
    except Exception as e:
        print(f"hook_post_tool_use error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
