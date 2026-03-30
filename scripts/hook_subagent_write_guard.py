#!/usr/bin/env python3
"""PreToolUse hook: restrict subagent Write/Edit to allowed directories.

Only fires for subagent contexts (agent_id present). Main session writes
are unrestricted. Subagents may only write to ~/.claude/agent-memory/.

Exit codes:
  0 — allow the tool call
  2 — block the tool call (stderr message fed back to Claude)
"""

import json
import os
import sys

ALLOWED_PREFIXES = [
    os.path.expanduser("~/.claude/agent-memory/"),
]


def main():
    try:
        data = json.loads(sys.stdin.read())
        if not isinstance(data, dict):
            sys.exit(0)  # Not a JSON object — fail open

        # Only enforce for subagents — main session is unrestricted
        if not data.get("agent_id"):
            sys.exit(0)

        tool_input = data.get("tool_input", {})
        if not isinstance(tool_input, dict):
            sys.exit(0)

        file_path = tool_input.get("file_path", "")
        if not file_path or not isinstance(file_path, str):
            sys.exit(0)  # No file path — allow (e.g. other tool params)

        # Strip null bytes before resolving
        file_path = file_path.replace("\x00", "")
        if not file_path:
            sys.exit(0)

        # Resolve to absolute path
        resolved = os.path.realpath(os.path.expanduser(file_path))

        for prefix in ALLOWED_PREFIXES:
            resolved_prefix = os.path.realpath(os.path.expanduser(prefix))
            if resolved.startswith(resolved_prefix):
                sys.exit(0)  # Within allowed directory

        # Block — path is outside allowed directories for subagents
        print(
            f"BLOCKED: Subagent write to '{file_path}' denied. "
            f"Subagents may only write to: {', '.join(ALLOWED_PREFIXES)}",
            file=sys.stderr,
        )
        sys.exit(2)

    except Exception:
        sys.exit(0)  # Any unexpected error — fail open


if __name__ == "__main__":
    main()
