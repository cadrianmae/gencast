#!/usr/bin/env bash
# PreToolUse hook: block string-form "author" in .claude-plugin/plugin.json.
# Claude Code's plugin schema requires the object form `{name, email}`; the
# string form silently fails the manifest validation, leaving the plugin
# uninstallable with no clear error. This trap bit the v1.2.0 cutover.
#
# Wired in .claude/settings.json under hooks.PreToolUse. Exit 2 = block edit.
set -e

f="${CLAUDE_TOOL_INPUT_file_path:-${CLAUDE_TOOL_INPUT_FILE_PATH:-}}"
[ -z "$f" ] && exit 0

case "$f" in
    *.claude-plugin/plugin.json)
        # The proposed new content is in either snake_case (current) or UPPER (fallback).
        # Edit tool uses new_string; Write tool uses content.
        c="${CLAUDE_TOOL_INPUT_new_string:-${CLAUDE_TOOL_INPUT_NEW_STRING:-${CLAUDE_TOOL_INPUT_content:-${CLAUDE_TOOL_INPUT_CONTENT:-}}}}"
        if echo "$c" | grep -qE '"author"[[:space:]]*:[[:space:]]*"'; then
            cat >&2 <<'EOF'
BLOCKED: plugin.json author must be an object {name, email}, not a string.

Claude Code silently fails the manifest schema check on the string form,
leaving the plugin uninstallable with no clear error. Use:

    "author": {
      "name": "Mae",
      "email": "45900436+cadrianmae@users.noreply.github.com"
    }

This guard is enforced by .claude/scripts/pre-edit-plugin-author-guard.sh
EOF
            exit 2
        fi
        ;;
esac
