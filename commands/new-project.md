Set up a new project with the standard docs pattern (README + CHANGELOG), git repo, GitHub remote, and .gitignore.

The project name comes from the user's input. If no name was provided, ask for one before proceeding.

Do the following steps:

---

### 1. Create project folder and initialize git

First, determine the workspace directory by reading `~/.claude-memory/workspace`. If the file exists, create the project there. If not, create it in the current working directory.

```bash
WORKSPACE=$(cat ~/.claude-memory/workspace 2>/dev/null || echo "$PWD")
mkdir -p $WORKSPACE/$PROJECT_NAME
cd $WORKSPACE/$PROJECT_NAME
git init -b main
```

Replace `$PROJECT_NAME` with a kebab-case version of the name (e.g., "My New API" -> "my-new-api").

---

### 2. Create README.md

This is the **source of truth** for current project state. Ask me for a brief description of the project, then create:

```markdown
# Project Name

Brief description (1-2 sentences).

## Status
- **Phase:** Setup
- **Status:** Active

## Tech Stack
- (fill in based on what the user describes)

## Quick Start
(to be filled in as project develops)

## Next Actions
- [ ] Initial task 1
- [ ] Initial task 2

## History
Full history: [CHANGELOG.md](./CHANGELOG.md)
```

---

### 3. Create CHANGELOG.md

```markdown
# Changelog

All significant changes to this project are documented here.

---
```

Keep it minimal. Entries will be added by `/checkpoint` and `/save`.

---

### 4. Create .gitignore

Start with the standard template and adapt based on the project's tech stack:

```
# Editor backups
*~
*.swp
*.swo
.*.swp

# OS files
.DS_Store
Thumbs.db

# Secrets and credentials
*.pem
*.key
id_rsa*
id_ed25519*
.env
.env.*
credentials.*
*.secret

# Machine-specific
*.log
*.pid
*.sock
```

Add language/framework-specific patterns based on the tech stack (e.g., `node_modules/`, `__pycache__/`, `target/`, `.venv/`).

---

### 5. Initial commit

```bash
git add README.md CHANGELOG.md .gitignore
git commit -m "Initial project setup"
```

---

### 6. Create GitHub remote (optional)

Check if `gh` CLI is available. If so:

```bash
gh repo create $GITHUB_USERNAME/$PROJECT_NAME --private --source . --remote origin --push
```

If `gh` is not installed or the user declines, skip this step and note that no remote was created.

Default to private. If the user wants public, they'll say so.

---

### 7. Save to memory DB

```
python3 -c "
import sys; sys.path.insert(0, '$HOME/.claude-memory/scripts')
import memory_db
conn = memory_db.init_db()
memory_db.save_work_context(conn, '$PROJECT_NAME', 'project-init', current_state='New project initialized', next_steps=[], active_files=['README.md', 'CHANGELOG.md'], git_branch='main')
conn.close()
"
```

---

### 8. Confirm

Show me:
- Project location
- GitHub repo URL (if created)
- What to do next: `/understand` to orient, then start working

$ARGUMENTS
