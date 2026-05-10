#!/usr/bin/env bash
# PostToolUse hook: auto-run `ruff format` on edited *.py files.
# Wired in .claude/settings.json under hooks.PostToolUse.
#
# Reads the edited file path from the Claude Code tool-input env var (snake_case
# in current versions, UPPER as a fallback). Silently no-ops on:
#   - Non-Python files
#   - Missing venv (collaborator hasn't run `pip install -e .` yet)
#   - ruff format failure (don't block the edit on a formatter blip)
set -e

f="${CLAUDE_TOOL_INPUT_file_path:-${CLAUDE_TOOL_INPUT_FILE_PATH:-}}"
[ -z "$f" ] && exit 0

case "$f" in
    *.py)
        if [ -x "./venv/bin/ruff" ]; then
            ./venv/bin/ruff format "$f" 2>/dev/null || true
        fi
        ;;
esac
