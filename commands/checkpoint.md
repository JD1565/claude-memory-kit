Quick mid-session progress checkpoint. Save a note to CHANGELOG.md and memory DB without committing or pushing.

Do the following steps:

1. **Validate location**: Check that `$PWD` is inside a git repository. If not, stop and tell me: "Not in a git repository. Navigate to a project first." Also check if `~/.claude-memory/workspace` exists — if so, verify `$PWD` is under that workspace path and warn if not.

2. **Gather context** by running these commands:
   - `git status --short`
   - `git branch --show-current`

3. **Read existing CHANGELOG.md** (first 30 lines) to understand the format. If no CHANGELOG.md exists, that's fine — you'll just skip the CHANGELOG write and only save to memory DB.

4. **Append a checkpoint entry** to CHANGELOG.md. Insert it right after the first `---` separator (after the header section), before existing date entries. Use this exact format:

   ```
   _Checkpoint [YYYY-MM-DD HH:MM]: <note>_

   ---

   ```

   Where `<note>` is expanded from the user's input below. Keep it on one line, italic, minimal. Don't add headers or bullet points — this is a lightweight waypoint, not a full entry.

5. **Save work_context to memory DB** by running:
   ```
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.claude-memory/scripts')
   import memory_db
   conn = memory_db.init_db()
   memory_db.save_work_context(conn, memory_db.derive_project_name('$PWD'), 'checkpoint', current_state='Checkpoint: <note>', active_files=[], git_branch='<branch>')
   conn.close()
   "
   ```
   Replace `<note>` with the checkpoint note and `<branch>` with the current git branch.

6. **Confirm** with a short message like:
   ```
   Checkpoint saved: <note>
   ```

Do NOT commit, push, or write a full session entry. This is a quick save.

$ARGUMENTS
