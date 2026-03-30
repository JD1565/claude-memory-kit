#!/usr/bin/env python3
"""
PreCompact hook: saves work context snapshot before context window compression.
Reads transcript tail, extracts state, saves to SQLite.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import memory_db


def get_git_info(cwd: str) -> tuple:
    """Get git branch and short status."""
    branch = None
    status = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            branch = result.stdout.strip()

        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=cwd, capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            status = result.stdout.strip()[:500]
    except Exception:
        pass
    return branch, status


def parse_transcript_tail(transcript_path: str, lines: int = 50) -> dict:
    """Read last N lines of transcript and extract useful info."""
    result = {
        "current_state": None,
        "recent_changes": [],
        "active_files": [],
        "next_steps": [],
    }

    if not transcript_path or not Path(transcript_path).exists():
        return result

    try:
        all_lines = []
        with open(transcript_path, "r") as f:
            for line in f:
                all_lines.append(line)
        tail = all_lines[-lines:]

        assistant_texts = []
        files_seen = set()

        for line in tail:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = entry.get("role", "")

            if role == "assistant":
                content = entry.get("content", "")
                if isinstance(content, str):
                    assistant_texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            assistant_texts.append(block.get("text", ""))
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            inp = block.get("input", {})
                            for key in ("file_path", "path", "pattern"):
                                if key in inp and isinstance(inp[key], str):
                                    val = inp[key]
                                    if "/" in val:
                                        files_seen.add(val)

            if role == "tool":
                content = entry.get("content", "")
                if isinstance(content, str):
                    for match in re.finditer(r'(/[\w./-]+\.\w+)', content):
                        fp = match.group(1)
                        if len(fp) < 200:
                            files_seen.add(fp)

        if assistant_texts:
            last_text = assistant_texts[-1][:500]
            result["current_state"] = last_text

        for text in reversed(assistant_texts[:10]):
            for match in re.finditer(r'[-*]\s+(.+?)(?:\n|$)', text):
                step = match.group(1).strip()
                if any(kw in step.lower() for kw in ["next", "todo", "need to", "should", "will"]):
                    result["next_steps"].append(step[:200])
            if result["next_steps"]:
                break

        result["active_files"] = list(files_seen)[:20]
        result["next_steps"] = result["next_steps"][:10]

    except Exception as e:
        print(f"transcript parse error: {e}", file=sys.stderr)

    return result


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception):
        return

    session_id = input_data.get("session_id", "")
    cwd = input_data.get("cwd", os.getcwd())
    transcript_path = input_data.get("transcript_path", "")
    project_name = memory_db.derive_project_name(cwd)

    try:
        conn = memory_db.init_db()
    except Exception as e:
        print(f"Failed to init DB: {e}", file=sys.stderr)
        return

    try:
        state = parse_transcript_tail(transcript_path)
        git_branch, git_status = get_git_info(cwd)

        memory_db.save_work_context(
            conn,
            project_name=project_name,
            session_id=session_id,
            current_state=state["current_state"],
            recent_changes=state["recent_changes"],
            next_steps=state["next_steps"],
            blockers=[],
            active_files=state["active_files"],
            git_branch=git_branch,
            git_status=git_status,
        )

        memory_db.increment_compaction(conn, session_id)

    except Exception as e:
        print(f"hook_pre_compact error: {e}", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
