#!/usr/bin/env python3
"""
Stop hook: captures decisions, learnings, and next steps after Claude responses.
Fires on every Stop event but exits fast if response isn't significant.
Uses keyword detection + heuristic regex extraction (no LLM calls).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Significance keywords — if none match, exit immediately
DECISION_KEYWORDS = {
    "decided", "decision", "chose", "chosen", "approach", "went with",
    "opted for", "selected", "picked", "architecture", "design choice",
    "trade-off", "tradeoff", "trade off", "instead of", "rather than",
    "alternative", "pros and cons",
}

LEARNING_KEYWORDS = {
    "learned", "gotcha", "caveat", "watch out", "turns out",
    "discovered", "realized", "important to note", "lesson",
    "workaround", "tip", "trick", "pattern", "best practice",
    "found that", "note to self",
}

CONTEXT_KEYWORDS = {
    "blocker", "blocked", "stuck", "next step", "todo", "need to",
    "remaining", "left to do", "still need", "upcoming",
}

ALL_KEYWORDS = DECISION_KEYWORDS | LEARNING_KEYWORDS | CONTEXT_KEYWORDS


def get_last_assistant_text(transcript_path: str) -> str:
    """Get the text from the last assistant message in the transcript."""
    if not transcript_path or not Path(transcript_path).exists():
        return ""

    try:
        last_assistant = ""
        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("role") == "assistant":
                    content = entry.get("content", "")
                    if isinstance(content, str):
                        last_assistant = content
                    elif isinstance(content, list):
                        texts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block.get("text", ""))
                        if texts:
                            last_assistant = "\n".join(texts)
        return last_assistant
    except Exception:
        return ""


def extract_session_summary(transcript_path: str) -> str:
    """Extract a meaningful session summary from the transcript.

    Scans assistant messages in reverse order, returns the last one
    that is >100 chars (substantive). Truncates to 200 chars.
    """
    if not transcript_path or not Path(transcript_path).exists():
        return ""

    try:
        candidates = []
        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("role") == "assistant":
                    content = entry.get("content", "")
                    text = ""
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        texts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block.get("text", ""))
                        text = "\n".join(texts)

                    if len(text) > 100:
                        candidates.append(text)

        if candidates:
            return candidates[-1][:200]
        return ""
    except Exception:
        return ""


def extract_recent_changes(cwd: str, session_start: str = None) -> list:
    """Get list of recent commit messages from git log."""
    try:
        cmd = ["git", "log", "--oneline", "--no-decorate"]
        if session_start:
            cmd.extend(["--since", session_start])
        else:
            cmd.extend(["-10"])

        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            return [line.split(" ", 1)[1] if " " in line else line for line in lines[:20]]
        return []
    except Exception:
        return []


def is_significant(text: str) -> tuple:
    """Quick keyword check. Returns (is_significant, matched_categories)."""
    if not text or len(text) < 50:
        return False, set()

    text_lower = text.lower()
    categories = set()

    for kw in DECISION_KEYWORDS:
        if kw in text_lower:
            categories.add("decision")
            break

    for kw in LEARNING_KEYWORDS:
        if kw in text_lower:
            categories.add("learning")
            break

    for kw in CONTEXT_KEYWORDS:
        if kw in text_lower:
            categories.add("context")
            break

    return bool(categories), categories


def extract_decisions(text: str) -> list:
    """Heuristic extraction of decisions from assistant text."""
    decisions = []

    patterns = [
        r'(?:decided|chose|opted|selected|went with|picking)\s+(?:to\s+)?(.+?)(?:\s+because\s+(.+?))?(?:\.|$)',
        r'(?:decision|approach|choice):\s*(.+?)(?:\.|$)',
        r'(?:trade-off|tradeoff):\s*(.+?)(?:\.|$)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            decision_text = match.group(1).strip()
            reasoning = match.group(2).strip() if match.lastindex >= 2 and match.group(2) else None

            if len(decision_text) > 10 and len(decision_text) < 500:
                decisions.append({
                    "title": decision_text[:100],
                    "decision": decision_text[:300],
                    "reasoning": reasoning[:300] if reasoning else None,
                })

    for match in re.finditer(r'([^.]+?(?:instead of|rather than)[^.]+)', text, re.IGNORECASE):
        choice_text = match.group(1).strip()
        if len(choice_text) > 15 and len(choice_text) < 500:
            decisions.append({
                "title": choice_text[:100],
                "decision": choice_text[:300],
                "reasoning": None,
            })

    return decisions[:3]


def extract_learnings(text: str) -> list:
    """Heuristic extraction of learnings/gotchas."""
    learnings = []

    patterns = [
        (r'(?:learned|discovered|realized|found)\s+(?:that\s+)?(.+?)(?:\.|$)', "pattern"),
        (r'(?:gotcha|caveat|watch out|important):\s*(.+?)(?:\.|$)', "gotcha"),
        (r'(?:workaround|trick|tip):\s*(.+?)(?:\.|$)', "workaround"),
        (r'(?:turns out|it turns out)\s+(?:that\s+)?(.+?)(?:\.|$)', "gotcha"),
    ]

    for pattern, category in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            learning_text = match.group(1).strip()
            if len(learning_text) > 10 and len(learning_text) < 500:
                learnings.append({
                    "category": category,
                    "title": learning_text[:100],
                    "description": learning_text[:300],
                })

    return learnings[:3]


def extract_next_steps(text: str) -> list:
    """Extract next steps / TODOs from text."""
    steps = []

    sections = re.split(r'\n(?:#{1,3}|[-*])\s', text)
    for section in sections:
        section_lower = section.lower()
        if any(kw in section_lower for kw in ["next step", "todo", "remaining", "left to do"]):
            for match in re.finditer(r'[-*]\s+(.+?)(?:\n|$)', section):
                step = match.group(1).strip()
                if len(step) > 5:
                    steps.append(step[:200])

    for match in re.finditer(r'(?:need to|should|will)\s+(.+?)(?:\.|$)', text, re.IGNORECASE):
        step = match.group(1).strip()
        if len(step) > 10 and len(step) < 200:
            steps.append(step)

    return steps[:10]


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception):
        return

    session_id = input_data.get("session_id", "")
    cwd = input_data.get("cwd", os.getcwd())
    transcript_path = input_data.get("transcript_path", "")

    # Skip non-project sessions (home dir, no git repo)
    cwd_resolved = Path(cwd).resolve()
    if cwd_resolved == Path.home() or not (cwd_resolved / ".git").exists():
        return

    # Claude Code provides last_assistant_message directly (preferred over transcript parsing)
    text = input_data.get("last_assistant_message", "")
    if not text:
        text = get_last_assistant_text(transcript_path)

    project_name = cwd_resolved.name or "unknown"

    import memory_db

    # --- Update session data on every Stop (keeps DB fresh) ---
    try:
        summary = text[:200] if text and len(text) > 100 else extract_session_summary(transcript_path)
        if summary:
            update_conn = memory_db.init_db()
            memory_db.update_session_data(update_conn, session_id, summary=summary)

            session_row = update_conn.execute(
                "SELECT started_at FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            started_at = session_row["started_at"] if session_row else None

            recent_changes = extract_recent_changes(cwd, session_start=started_at)
            if recent_changes:
                memory_db.save_work_context(
                    update_conn,
                    project_name=project_name,
                    session_id=session_id,
                    current_state=summary,
                    recent_changes=recent_changes,
                )
            update_conn.close()
    except Exception:
        pass

    # --- Keyword-gated DB extraction (decisions, learnings, context) ---

    significant, categories = is_significant(text)
    if not significant:
        return

    try:
        conn = memory_db.init_db()
    except Exception as e:
        print(f"Failed to init DB: {e}", file=sys.stderr)
        return

    try:
        if "decision" in categories:
            for d in extract_decisions(text):
                memory_db.add_decision(
                    conn, session_id, project_name,
                    title=d["title"],
                    decision=d["decision"],
                    reasoning=d["reasoning"],
                )

        if "learning" in categories:
            for l in extract_learnings(text):
                memory_db.add_learning(
                    conn, session_id, project_name,
                    category=l["category"],
                    title=l["title"],
                    description=l["description"],
                )

        if "context" in categories:
            next_steps = extract_next_steps(text)
            if next_steps:
                memory_db.save_work_context(
                    conn,
                    project_name=project_name,
                    session_id=session_id,
                    current_state=text[:300] if text else None,
                    next_steps=next_steps,
                )

    except Exception as e:
        print(f"hook_stop error: {e}", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
