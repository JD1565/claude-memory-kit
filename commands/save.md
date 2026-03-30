End-of-session save. Write a full CHANGELOG entry, save to memory DB, git commit, and push.

If no summary was provided after this instruction block, ask me for a brief summary of what we accomplished before proceeding.

Do the following steps:

---

### 1. Validate location

Check both of these conditions:

1. `$PWD` is inside the workspace directory. Read the workspace path from `~/.claude-memory/workspace` (one line, e.g. `/home/user/Claude`). If the file doesn't exist, skip this check. If `$PWD` is not under the workspace, warn: "Not inside your workspace directory (<path>). Continue anyway? [y/N]" and stop unless confirmed.

2. `$PWD` is inside a git repository (`git rev-parse --git-dir`). If not, stop and tell me: "Not in a git repository. Navigate to a project first."

---

### 2. Gather session data

Run these commands to understand the session:

- `git status` — see all changes
- `git diff --stat` — change summary
- `git branch --show-current` — current branch
- `python3 ~/.claude-memory/scripts/get_session_info.py` — get session start time
- Read the project's CHANGELOG.md (first 50 lines) to learn its format. If none exists, you'll create one.

Then, using the session start time from get_session_info.py:
- `git log --oneline --since="<started_at>"` — commits made this session

Also query memory DB for latest work_context:
```
python3 -c "
import sys, json; sys.path.insert(0, '$HOME/.claude-memory/scripts')
import memory_db
conn = memory_db.init_db()
ctx = memory_db.get_latest_work_context(conn, memory_db.derive_project_name('$PWD'))
conn.close()
if ctx: print(json.dumps({k: ctx[k] for k in ['current_state','next_steps','active_files'] if ctx.get(k)}, indent=2))
else: print('No work context found')
"
```

---

### 3. Draft and write CHANGELOG entry

Read the existing CHANGELOG.md format carefully and generate a matching entry. If no CHANGELOG.md exists, create one with this header first:

```markdown
# Changelog

All significant changes to this system are documented here.

---
```

Then insert a new entry **after the first `---` separator** (after the header), before existing date entries. Typical structure:

```markdown
## [YYYY-MM-DD] Session: HH:MM

### Summary
<expanded from user's summary + observed changes>

### Changes
- <derived from git diff --stat and session context>

### Git Commits
- `hash` - message

### Next Steps
- [ ] <inferred from current state>

---
```

Adapt the format to match the existing CHANGELOG style for this project. The key is consistency with what's already there.

Remove any previous checkpoint entries (lines matching `_Checkpoint [.*]:.*_`) that were made during this session — they're superseded by this full entry.

---

### 4. Save to memory DB

Save final work_context and close the session:
```
python3 -c "
import sys, json; sys.path.insert(0, '$HOME/.claude-memory/scripts')
import memory_db
conn = memory_db.init_db()
info_row = conn.execute('SELECT session_id, project_name FROM sessions WHERE project_path LIKE ? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1', ('%' + '$PWD'.split('/')[-1],)).fetchone()
if info_row:
    sid, pname = info_row['session_id'], info_row['project_name']
    memory_db.save_work_context(conn, pname, sid, current_state='<CURRENT_STATE>', next_steps=<NEXT_STEPS_LIST>, active_files=<ACTIVE_FILES_LIST>, git_branch='<BRANCH>')
    memory_db.close_session(conn, sid, summary='<SUMMARY>', next_steps=<NEXT_STEPS_LIST>)
else:
    pname = memory_db.derive_project_name('$PWD')
    memory_db.save_work_context(conn, pname, 'manual-save', current_state='<CURRENT_STATE>', next_steps=<NEXT_STEPS_LIST>, active_files=<ACTIVE_FILES_LIST>, git_branch='<BRANCH>')
conn.close()
print('Memory DB updated')
"
```

Replace the `<PLACEHOLDERS>` with actual values. `<NEXT_STEPS_LIST>` and `<ACTIVE_FILES_LIST>` should be Python lists like `['item1', 'item2']`. `<SUMMARY>` and `<CURRENT_STATE>` should be strings.

---

### 5. Git commit and push

Stage, commit, and push safely:

1. **Review what will be staged.** Run `git status --short` and show me the list of files that would be added. Look for anything suspicious:
   - Files matching common secret patterns (`.env`, `*.pem`, `*.key`, `id_*`, `credentials.*`, `*.secret`)
   - Binary files or large files that don't belong in the repo
   If you spot anything dangerous, **warn me and skip staging those files**. Only proceed with safe files.

2. **Stage files explicitly.** Instead of `git add -A`, stage files by name — add tracked/modified files and any new files that clearly belong in the repo. If there are many safe files and .gitignore is comprehensive, you can use `git add -A`.

3. Check if there are changes to commit with `git diff --cached --quiet`. If no changes, say "No changes to commit" and skip to step 6.

4. Commit with message based on the session summary. Use this format:
   ```
   git commit -m "$(cat <<'EOF'
   <concise summary>

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   ```

5. **Sync and push to remote:**
   - First check if a remote exists: `git remote -v`
   - If no remote, warn "No git remote configured — skipping push" and continue
   - If remote exists, **pull before pushing** to handle multi-machine divergence:
     - `git pull --rebase`
     - If the rebase fails due to conflicts, **stop and tell me** — do not force push or auto-resolve
   - Then push:
     - Check for upstream: `git rev-parse --abbrev-ref @{upstream} 2>/dev/null`
     - If no upstream: `git push -u origin <branch>`
     - If upstream exists: `git push`

6. Report the result

---

### 6. Present summary

Show me a concise summary:
- What was appended to CHANGELOG
- Commit hash and push status
- Next steps (if any)

$ARGUMENTS
