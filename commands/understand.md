Understand the current project by reading its key documentation files. Do the following:

1. Look for and read these files in the project root (skip any that don't exist):
   - README.md (or README)
   - CHANGELOG.md (or CHANGELOG)
   - CLAUDE.md
   - package.json, pyproject.toml, or Cargo.toml (just for project name/description)

2. Summarize what you learned in a concise overview:
   - What the project does (1-2 sentences)
   - Key technologies/stack
   - Current state (from changelog: what was done recently)
   - Project structure (list the main directories/modules if apparent from the docs)

3. Save a work_context snapshot to the memory system by running:
   ```
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.claude-memory/scripts')
   import memory_db
   conn = memory_db.init_db()
   memory_db.save_work_context(conn, memory_db.derive_project_name('$PWD'), 'manual-understand', current_state='''<INSERT_SUMMARY>''', next_steps=[], active_files=[])
   conn.close()
   "
   ```
   Replace <INSERT_SUMMARY> with a 1-2 sentence summary of the project's current state.

4. Present the overview to me clearly. Keep it short — this is orientation, not deep analysis.

$ARGUMENTS
