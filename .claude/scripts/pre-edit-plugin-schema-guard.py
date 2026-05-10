#!/usr/bin/env python3
"""PreToolUse hook: validate Claude Code plugin file schemas before writes commit.

Replaces the prior single-trap author-guard with a full schema enforcer covering:

    .claude-plugin/plugin.json       — plugin manifest
    .claude-plugin/marketplace.json  — marketplace listing
    skills/<name>/SKILL.md           — skill frontmatter (body excluded)
    agents/<name>.md                 — agent frontmatter (body excluded)
    commands/<name>.md               — command frontmatter (body excluded)
    hooks/hooks.json                 — hook configuration
    .mcp.json                        — MCP server configuration

Exit semantics (per Claude Code hook convention):
    0 = allow the edit (file does not match a known plugin shape, OR validates clean)
    2 = block the edit (parsed file fails schema; stderr message guides the fix)

Partial Edit tool calls usually leave new_string non-parseable (e.g. just a bumped
version number) — these silently allow. Full-file Write tool calls always
parse + validate. The retained substring author-guard catches partial-Edit hits
on the v1.2.0-style author-string trap for plugin.json specifically.

Schema sources (no Anthropic-shipped JSON Schemas exist):
    https://code.claude.com/docs/en/plugins-reference.md
    https://code.claude.com/docs/en/skills.md
    https://code.claude.com/docs/en/hooks.md
    https://code.claude.com/docs/en/mcp.md
    https://code.claude.com/docs/en/plugin-marketplaces.md
"""
from __future__ import annotations

import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SEMVER_RE = re.compile(r"^\d+(\.\d+){0,2}([a-z0-9.+-]*)?$")

VALID_HOOK_EVENTS = frozenset({
    "SessionStart", "Setup", "UserPromptSubmit", "UserPromptExpansion",
    "PreToolUse", "PermissionRequest", "PermissionDenied", "PostToolUse",
    "PostToolUseFailure", "PostToolBatch", "Notification",
    "SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted",
    "Stop", "StopFailure", "TeammateIdle", "InstructionsLoaded",
    "ConfigChange", "CwdChanged", "FileChanged",
    "WorktreeCreate", "WorktreeRemove", "PreCompact", "PostCompact",
    "Elicitation", "ElicitationResult", "SessionEnd",
})

VALID_HOOK_TYPES = frozenset({"command", "http", "mcp_tool", "prompt", "agent"})
VALID_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
VALID_SOURCE_KINDS = frozenset({"github", "url", "git-subdir", "npm"})


# ---------------------------------------------------------------------------
# Tiny YAML frontmatter parser — stdlib-only, just enough for our checks
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter between --- markers. Returns None if absent."""
    if not content.startswith("---\n"):
        return None
    end_marker = content.find("\n---", 4)
    if end_marker < 0:
        return None
    raw = content[4:end_marker]
    out: dict = {}
    for line in raw.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        if line.startswith(" ") or line.startswith("\t"):
            continue  # nested — skip; our validators only check top-level keys
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if not val or val.startswith("|") or val.startswith(">"):
            out[key] = ""  # multi-line — placeholder, we only care it exists
            continue
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        elif val in ("true", "false"):
            val = val == "true"
        elif val.lstrip("-").isdigit():
            val = int(val)
        out[key] = val
    return out


# ---------------------------------------------------------------------------
# Validators — each returns a list of error strings (empty = pass)
# ---------------------------------------------------------------------------

def validate_plugin_json(content: str) -> list[str]:
    """Plugin manifest. Most aggressive checks because this is where v1.2.0 broke."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Substring fallback for partial edits that don't parse
        if re.search(r'"author"\s*:\s*"', content):
            return ['author must be an object {name, email}, not a string '
                    '(silently fails Claude Code\'s manifest schema)']
        return []

    if not isinstance(data, dict):
        return ["plugin.json root must be an object"]

    errs: list[str] = []
    if "name" not in data:
        errs.append("missing required field: name")
    elif not isinstance(data["name"], str) or not KEBAB_RE.match(data["name"]):
        errs.append(f'name must be kebab-case (lowercase + digits + - / _), got: {data.get("name")!r}')

    if "version" in data and isinstance(data["version"], str):
        if not SEMVER_RE.match(data["version"]):
            errs.append(f'version should look like semver (e.g. "1.2.3"), got: {data["version"]!r}')

    if "author" in data and not isinstance(data["author"], dict):
        errs.append('author must be an object {name, email?, url?}, not a string '
                    '(silently fails Claude Code\'s manifest schema — the v1.2.0 trap)')
    elif isinstance(data.get("author"), dict) and "name" not in data["author"]:
        errs.append("author.name is required")

    for arr_field in ("keywords", "skills", "commands", "agents"):
        if arr_field in data:
            v = data[arr_field]
            if not isinstance(v, (str, list, dict)):
                errs.append(f"{arr_field} must be string, array, or object — got {type(v).__name__}")

    if "requires" in data:
        if not isinstance(data["requires"], dict):
            errs.append("requires must be an object")
        elif "system" in data["requires"] and not isinstance(data["requires"]["system"], list):
            errs.append("requires.system must be an array of strings")

    return errs


def validate_marketplace_json(content: str) -> list[str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict):
        return ["marketplace.json root must be an object"]

    errs: list[str] = []
    for f in ("name", "owner", "plugins"):
        if f not in data:
            errs.append(f"missing required field: {f}")

    if isinstance(data.get("owner"), str):
        errs.append("owner must be an object {name, email}, not a string")

    plugins = data.get("plugins", [])
    if not isinstance(plugins, list):
        errs.append("plugins must be an array")
    else:
        for i, p in enumerate(plugins):
            prefix = f"plugins[{i}]"
            if not isinstance(p, dict):
                errs.append(f"{prefix} must be an object")
                continue
            if "name" not in p:
                errs.append(f"{prefix}.name is required")
            if "source" not in p:
                errs.append(f"{prefix}.source is required")
            else:
                src = p["source"]
                if isinstance(src, str):
                    if not src.startswith("./"):
                        errs.append(
                            f"{prefix}.source path strings must start with './' — got {src!r} "
                            "(use './<dir>' or the object form for github/url/git-subdir/npm)"
                        )
                elif isinstance(src, dict):
                    kind = src.get("source")
                    if kind not in VALID_SOURCE_KINDS:
                        errs.append(f'{prefix}.source.source must be one of {sorted(VALID_SOURCE_KINDS)}, '
                                    f"got: {kind!r}")
                    elif kind == "github" and "repo" not in src:
                        errs.append(f"{prefix}.source needs 'repo' for github source")
                    elif kind == "url" and "url" not in src:
                        errs.append(f"{prefix}.source needs 'url' for url source")
                    elif kind == "git-subdir" and ("url" not in src or "path" not in src):
                        errs.append(f"{prefix}.source needs 'url' and 'path' for git-subdir source")
                    elif kind == "npm" and "package" not in src:
                        errs.append(f"{prefix}.source needs 'package' for npm source")
                else:
                    errs.append(f"{prefix}.source must be a relative path string or source object")
            if "author" in p and not isinstance(p["author"], dict):
                errs.append(f"{prefix}.author must be object {{name, email}}, not string "
                            "(same trap as plugin.json author)")

    return errs


def _validate_md_frontmatter(content: str, kind: str, required: tuple, enums: dict) -> list[str]:
    """Shared frontmatter validator for SKILL.md / agent.md / command.md."""
    fm = parse_frontmatter(content)
    if fm is None:
        # No frontmatter — only flag if the content looks like a write of the
        # whole file (starts with `#` heading would be weird without frontmatter)
        return []

    errs: list[str] = []
    for f in required:
        if f not in fm:
            errs.append(f"{kind} frontmatter missing required field: {f}")
    if "name" in fm:
        v = fm["name"]
        if not isinstance(v, str) or not KEBAB_RE.match(v):
            errs.append(f"{kind} name must be kebab-case 1-64 chars (^[a-z0-9_-]+$), got: {v!r}")
        elif len(v) > 64:
            errs.append(f"{kind} name must be ≤64 chars")
    if "description" in fm and isinstance(fm["description"], str):
        if len(fm["description"]) > 1536:
            errs.append(f"{kind} description should be ≤1536 chars (got {len(fm['description'])})")

    for field, allowed in enums.items():
        if field in fm and fm[field] not in allowed:
            errs.append(f"{kind}.{field} must be one of {sorted(allowed)}, got: {fm[field]!r}")

    return errs


def validate_skill_frontmatter(content: str) -> list[str]:
    return _validate_md_frontmatter(
        content, "SKILL.md",
        required=("name", "description"),
        enums={"effort": VALID_EFFORTS, "context": frozenset({"fork"})},
    )


def validate_agent_frontmatter(content: str) -> list[str]:
    errs = _validate_md_frontmatter(
        content, "agent",
        required=("name", "description"),
        enums={"effort": VALID_EFFORTS, "isolation": frozenset({"worktree"})},
    )
    fm = parse_frontmatter(content) or {}
    # Plugin agents MUST NOT specify these
    for forbidden in ("hooks", "mcpServers", "permissionMode"):
        if forbidden in fm:
            errs.append(f"agent frontmatter cannot specify '{forbidden}' (plugin-agent restriction)")
    return errs


def validate_command_frontmatter(content: str) -> list[str]:
    return _validate_md_frontmatter(
        content, "command",
        required=("description",),  # name comes from filename
        enums={"effort": VALID_EFFORTS},
    )


def validate_hooks_json(content: str) -> list[str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    errs: list[str] = []
    # Accept both top-level event-keyed and nested-under-"hooks" shapes
    events = data.get("hooks", data) if isinstance(data, dict) else None
    if not isinstance(events, dict):
        return ["hooks.json must be an object keyed by event name"]

    for event_name, entries in events.items():
        if event_name not in VALID_HOOK_EVENTS:
            errs.append(f"unknown hook event {event_name!r}; "
                        f"valid events include PreToolUse, PostToolUse, SessionStart, ...")
        if not isinstance(entries, list):
            errs.append(f"hooks.{event_name} must be an array of {{matcher, hooks}} objects")
            continue
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errs.append(f"hooks.{event_name}[{i}] must be an object")
                continue
            if "hooks" not in entry:
                errs.append(f"hooks.{event_name}[{i}] missing required field 'hooks'")
                continue
            for j, h in enumerate(entry["hooks"]):
                if not isinstance(h, dict):
                    errs.append(f"hooks.{event_name}[{i}].hooks[{j}] must be an object")
                    continue
                if "type" not in h:
                    errs.append(f"hooks.{event_name}[{i}].hooks[{j}] missing 'type'")
                elif h["type"] not in VALID_HOOK_TYPES:
                    errs.append(f"hooks.{event_name}[{i}].hooks[{j}].type must be one of "
                                f"{sorted(VALID_HOOK_TYPES)}, got: {h['type']!r}")
    return errs


def validate_mcp_json(content: str) -> list[str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict):
        return [".mcp.json root must be an object"]
    if "mcpServers" not in data:
        return ["missing required top-level 'mcpServers' object"]
    servers = data["mcpServers"]
    if not isinstance(servers, dict):
        return ["mcpServers must be an object keyed by server name"]

    errs: list[str] = []
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            errs.append(f"mcpServers.{name} must be an object")
            continue
        if "command" not in cfg:
            errs.append(f"mcpServers.{name} missing required 'command'")
        if "args" in cfg and not isinstance(cfg["args"], list):
            errs.append(f"mcpServers.{name}.args must be an array of strings")
        if "env" in cfg and not isinstance(cfg["env"], dict):
            errs.append(f"mcpServers.{name}.env must be an object")
    return errs


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

DISPATCH: list[tuple] = [
    (re.compile(r"\.claude-plugin/plugin\.json$"), validate_plugin_json),
    (re.compile(r"\.claude-plugin/marketplace\.json$"), validate_marketplace_json),
    (re.compile(r"(^|/)skills/[^/]+/SKILL\.md$"), validate_skill_frontmatter),
    (re.compile(r"(^|/)agents/[^/]+\.md$"), validate_agent_frontmatter),
    (re.compile(r"(^|/)commands/[^/]+\.md$"), validate_command_frontmatter),
    (re.compile(r"(^|/)hooks/hooks\.json$"), validate_hooks_json),
    (re.compile(r"\.mcp\.json$"), validate_mcp_json),
]


def main() -> int:
    fp = (
        os.environ.get("CLAUDE_TOOL_INPUT_file_path")
        or os.environ.get("CLAUDE_TOOL_INPUT_FILE_PATH")
        or ""
    )
    if not fp:
        return 0

    content = (
        os.environ.get("CLAUDE_TOOL_INPUT_new_string")
        or os.environ.get("CLAUDE_TOOL_INPUT_NEW_STRING")
        or os.environ.get("CLAUDE_TOOL_INPUT_content")
        or os.environ.get("CLAUDE_TOOL_INPUT_CONTENT")
        or ""
    )
    if not content:
        return 0

    for pattern, validator in DISPATCH:
        if pattern.search(fp):
            errors = validator(content)
            if errors:
                print(f"BLOCKED: {fp} fails plugin schema validation:", file=sys.stderr)
                for e in errors:
                    print(f"  - {e}", file=sys.stderr)
                print("\nThis guard is enforced by .claude/scripts/pre-edit-plugin-schema-guard.py",
                      file=sys.stderr)
                return 2
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
