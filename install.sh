#!/usr/bin/env bash
set -euo pipefail

# Claude Memory Kit — Installer
# Installs the memory system, hooks, and commands for Claude Code.
#
# Usage:
#   ./install.sh              # Interactive install
#   ./install.sh --dry-run    # Show what would be done without changing anything
#   ./install.sh --uninstall  # Remove installed files (keeps memory.db)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMORY_DIR="$HOME/.claude-memory"
SCRIPTS_DIR="$MEMORY_DIR/scripts"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
SETTINGS_FILE="$CLAUDE_DIR/settings.local.json"
WORKSPACE_DIR=""  # Set during install

DRY_RUN=false
UNINSTALL=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --uninstall) UNINSTALL=true ;;
    --help|-h)
      echo "Usage: ./install.sh [--dry-run] [--uninstall]"
      echo ""
      echo "  --dry-run     Show what would be done without making changes"
      echo "  --uninstall   Remove installed files (preserves memory.db)"
      exit 0
      ;;
  esac
done

info()  { echo -e "${BLUE}[info]${NC}  $1"; }
ok()    { echo -e "${GREEN}[ok]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $1"; }
err()   { echo -e "${RED}[error]${NC} $1"; }
dry()   { echo -e "${YELLOW}[dry]${NC}   $1"; }

# ── Uninstall ──

if $UNINSTALL; then
  info "Uninstalling Claude Memory Kit..."

  files=(
    "$SCRIPTS_DIR/memory_db.py"
    "$SCRIPTS_DIR/hook_session_start.py"
    "$SCRIPTS_DIR/hook_pre_compact.py"
    "$SCRIPTS_DIR/hook_stop.py"
    "$SCRIPTS_DIR/hook_post_tool_use.py"
    "$SCRIPTS_DIR/hook_subagent_write_guard.py"
    "$SCRIPTS_DIR/get_session_info.py"
    "$COMMANDS_DIR/save.md"
    "$COMMANDS_DIR/checkpoint.md"
    "$COMMANDS_DIR/understand.md"
    "$COMMANDS_DIR/new-project.md"
  )

  for f in "${files[@]}"; do
    if [ -f "$f" ]; then
      if $DRY_RUN; then
        dry "Would remove: $f"
      else
        rm "$f"
        ok "Removed: $f"
      fi
    fi
  done

  warn "Kept $MEMORY_DIR/memory.db (your session history)"
  warn "Kept $SETTINGS_FILE (review and remove hook entries manually)"
  info "Uninstall complete."
  exit 0
fi

# ── Pre-flight checks ──

info "Claude Memory Kit — Installer"
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
  err "python3 is required but not found. Install Python 3.9+ first."
  exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  err "Python 3.9+ required (found $PY_VERSION)"
  exit 1
fi
ok "Python $PY_VERSION"

# Check git
if ! command -v git &>/dev/null; then
  err "git is required but not found."
  exit 1
fi
ok "git $(git --version | awk '{print $3}')"

# Check Claude Code
if ! command -v claude &>/dev/null; then
  warn "Claude Code CLI not found in PATH. Install it first: https://docs.anthropic.com/en/docs/claude-code"
  warn "Continuing anyway — files will be installed for when you do."
fi

# Check for existing settings
if [ -f "$SETTINGS_FILE" ]; then
  warn "Existing settings.local.json found — hooks will be MERGED (existing hooks preserved)"
fi

echo ""

# ── Choose workspace directory ──

if ! $DRY_RUN; then
  info "Choose a workspace directory."
  echo "  This is where all your Claude Code projects will live."
  echo "  Each project gets its own subfolder with git, README, and CHANGELOG."
  echo ""
  echo "  Recommended: ~/Claude (general use) or ~/Dev (development only)"
  echo ""
  read -rp "Workspace directory [~/Claude]: " ws_input
  ws_input="${ws_input:-$HOME/Claude}"
  # Expand ~ if user typed it
  WORKSPACE_DIR="${ws_input/#\~/$HOME}"
else
  WORKSPACE_DIR="$HOME/Claude"
fi

# ── Confirm ──

if ! $DRY_RUN; then
  echo ""
  info "This will install to:"
  echo "  Scripts:    $SCRIPTS_DIR/"
  echo "  Commands:   $COMMANDS_DIR/"
  echo "  Database:   $MEMORY_DIR/memory.db (created on first session)"
  echo "  Config:     $SETTINGS_FILE (hooks added)"
  echo "  Workspace:  $WORKSPACE_DIR/ (project root)"
  echo ""
  read -rp "Proceed? [Y/n] " confirm
  if [[ "$confirm" =~ ^[Nn] ]]; then
    info "Aborted."
    exit 0
  fi
fi

# ── Install scripts ──

info "Installing core scripts..."

if $DRY_RUN; then
  dry "Would create: $SCRIPTS_DIR/"
  for f in memory_db.py hook_session_start.py hook_pre_compact.py hook_stop.py hook_post_tool_use.py hook_subagent_write_guard.py get_session_info.py; do
    dry "Would copy: scripts/$f -> $SCRIPTS_DIR/$f"
  done
else
  mkdir -p "$SCRIPTS_DIR"
  for f in memory_db.py hook_session_start.py hook_pre_compact.py hook_stop.py hook_post_tool_use.py hook_subagent_write_guard.py get_session_info.py; do
    cp "$SCRIPT_DIR/scripts/$f" "$SCRIPTS_DIR/$f"
    ok "Installed $f"
  done
fi

# ── Install commands ──

info "Installing slash commands..."

if $DRY_RUN; then
  dry "Would create: $COMMANDS_DIR/"
  for f in save.md checkpoint.md understand.md new-project.md; do
    dry "Would copy: commands/$f -> $COMMANDS_DIR/$f"
  done
else
  mkdir -p "$COMMANDS_DIR"
  for f in save.md checkpoint.md understand.md new-project.md; do
    # Don't overwrite existing commands without asking
    if [ -f "$COMMANDS_DIR/$f" ]; then
      warn "$f already exists. Overwrite? [y/N]"
      read -rp "  " overwrite
      if [[ ! "$overwrite" =~ ^[Yy] ]]; then
        warn "Skipped $f"
        continue
      fi
    fi
    cp "$SCRIPT_DIR/commands/$f" "$COMMANDS_DIR/$f"
    ok "Installed $f"
  done
fi

# ── Configure hooks in settings.local.json ──

info "Configuring hooks..."

HOOKS_JSON=$(cat <<'HOOKEOF'
{
  "SessionStart": [
    {
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "command": "python3 SCRIPTS_DIR_PLACEHOLDER/hook_session_start.py",
          "timeout": 8000
        }
      ]
    }
  ],
  "PreCompact": [
    {
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "command": "python3 SCRIPTS_DIR_PLACEHOLDER/hook_pre_compact.py",
          "timeout": 5000
        }
      ]
    }
  ],
  "Stop": [
    {
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "command": "python3 SCRIPTS_DIR_PLACEHOLDER/hook_stop.py",
          "timeout": 5000
        }
      ]
    }
  ],
  "PostToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "python3 SCRIPTS_DIR_PLACEHOLDER/hook_post_tool_use.py",
          "timeout": 3000
        }
      ]
    }
  ],
  "PreToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {
          "type": "command",
          "command": "python3 SCRIPTS_DIR_PLACEHOLDER/hook_subagent_write_guard.py",
          "timeout": 3000
        }
      ]
    }
  ]
}
HOOKEOF
)

# Replace placeholder with actual path
HOOKS_JSON="${HOOKS_JSON//SCRIPTS_DIR_PLACEHOLDER/$SCRIPTS_DIR}"

if $DRY_RUN; then
  dry "Would add memory hooks to $SETTINGS_FILE"
else
  mkdir -p "$CLAUDE_DIR"

  if [ -f "$SETTINGS_FILE" ]; then
    # Merge hooks into existing settings using Python
    python3 - "$SETTINGS_FILE" "$HOOKS_JSON" <<'PYEOF'
import json, sys

settings_path = sys.argv[1]
new_hooks = json.loads(sys.argv[2])

with open(settings_path) as f:
    settings = json.load(f)

existing_hooks = settings.get("hooks", {})

# For each hook event, append new entries (avoid duplicates by checking command string)
for event, entries in new_hooks.items():
    if event not in existing_hooks:
        existing_hooks[event] = entries
    else:
        # Check if memory hook already registered
        existing_commands = set()
        for entry in existing_hooks[event]:
            for h in entry.get("hooks", []):
                existing_commands.add(h.get("command", ""))
        for entry in entries:
            for h in entry.get("hooks", []):
                if h.get("command", "") not in existing_commands:
                    existing_hooks[event].append(entry)

settings["hooks"] = existing_hooks
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print("Merged hooks into existing settings")
PYEOF
    ok "Merged hooks into existing settings.local.json"
  else
    # Create new settings file
    python3 -c "
import json
hooks = json.loads('''$HOOKS_JSON''')
settings = {'hooks': hooks, 'permissions': {'defaultMode': 'default'}}
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')
"
    ok "Created settings.local.json with hooks"
  fi
fi

# ── Create workspace directory and install CLAUDE.md ──

info "Setting up workspace..."

if $DRY_RUN; then
  dry "Would create: $WORKSPACE_DIR/"
  dry "Would install CLAUDE.md to $WORKSPACE_DIR/CLAUDE.md"
else
  mkdir -p "$WORKSPACE_DIR"
  ok "Created $WORKSPACE_DIR/"

  if [ -f "$WORKSPACE_DIR/CLAUDE.md" ]; then
    warn "CLAUDE.md already exists in workspace — skipping"
  else
    # Replace placeholder in template with actual workspace path
    sed "s|~/Claude|$WORKSPACE_DIR|g" "$SCRIPT_DIR/templates/CLAUDE.md" > "$WORKSPACE_DIR/CLAUDE.md"
    ok "Installed CLAUDE.md to $WORKSPACE_DIR/"
  fi
fi

# ── Save workspace path for commands ──

if ! $DRY_RUN; then
  echo "$WORKSPACE_DIR" > "$MEMORY_DIR/workspace"
  ok "Saved workspace path to $MEMORY_DIR/workspace"
fi

# ── Summary ──

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if $DRY_RUN; then
  info "Dry run complete. No changes made."
else
  echo -e "${GREEN}Installation complete!${NC}"
  echo ""
  echo "What was installed:"
  echo "  - 7 Python scripts in $SCRIPTS_DIR/"
  echo "  - 4 slash commands in $COMMANDS_DIR/"
  echo "  - Hook registration in $SETTINGS_FILE"
  echo ""
  echo "Next steps:"
  echo "  1. cd $WORKSPACE_DIR"
  echo "  2. Use /new-project to create your first project"
  echo "  3. Start working — the memory system activates automatically"
  echo "  4. Use /checkpoint for mid-session saves"
  echo "  5. Use /save at end of session (writes CHANGELOG + git commit + push)"
  echo ""
  echo "The SQLite database is created automatically on first session at:"
  echo "  $MEMORY_DIR/memory.db"
  echo ""
  echo "Read the full guide: $SCRIPT_DIR/README.md"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
