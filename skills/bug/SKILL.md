---
name: gencast-bug
description: This skill should be used when the user asks to "file a gencast bug", "report a bug in gencast", "log a gencast issue", or otherwise wants to track a gencast defect. Files bug reports as GitHub issues on cadrianmae/gencast. For LOGGING only — does not attempt to fix the bug in this session.
allowed-tools: Bash, AskUserQuestion
argument-hint: <bug description>
---

# File a gencast bug report

Log a gencast bug as a GitHub issue on `cadrianmae/gencast`. This skill is for tracking only — do NOT attempt to diagnose or fix the bug in this session. The user will pick the issue up separately.

## Quick example

```
/gencast:bug estimate --rates-only --json prints empty dict for openai when ANTHROPIC_API_KEY missing
```

## Prerequisites

- `gh` CLI authenticated against `cadrianmae/gencast`. Verify with: !`gh auth status 2>&1 | grep -E "Logged in|Token" | head -1 || echo "MISSING — run: gh auth login"`
- Installed gencast version (so the bug can be tagged accurately): !`gencast --version 2>/dev/null || echo "(not installed — bug-report still works but version field will be 'unknown')"`

## Workflow

1. Ask 1–2 clarifying questions if the description is unclear:
   - What were the steps to reproduce?
   - What was expected vs what actually happened?
2. Determine which gencast component is affected — infer from conversation context, the description, or ask. Common components: `cli`, `pipeline:outline`, `pipeline:transcript`, `pipeline:audio`, `pipeline:estimate`, `tts`, `llm`, `profiles`, `plugin`, `docs`.
3. Capture the installed gencast version (the prereq check above).
4. Compose the issue title and body using the template below.
5. File with `gh issue create` against `cadrianmae/gencast` with labels `bug` + `component:<name>` + `version:<x.y.z>`.
6. Reply with the issue URL and return to the user's prior work.

## Issue creation

```bash
gh issue create \
  --repo cadrianmae/gencast \
  --title "<concise bug title>" \
  --body "<issue body>" \
  --label bug \
  --label "component:<name>" \
  --label "version:<x.y.z>"
```

### Body template

```markdown
## Description
<clarified description>

## Steps to Reproduce
<from clarifying questions, or 'Not specified' if user skipped>

## Expected Behaviour
<from clarifying questions, or 'Not specified' if user skipped>

## Environment
- gencast version: `<x.y.z>` (from `gencast --version`)
- Python: `<x.y>` (from `python3 --version`)
- OS: `<linux|macos|windows>`
- Profile (if applicable): `<speaker/episode/room name>`

---
Component: `<component>`
Date: <YYYY-MM-DD>
```

## After filing

Respond with the issue URL, e.g.:

> "gencast bug filed: https://github.com/cadrianmae/gencast/issues/42. Continuing with your current work."

Then return focus to whatever the user was doing before this command.

## What to NOT do

- Do not attempt to fix the bug in the same session — this skill is for logging.
- Do not file duplicates without checking: search first via `gh issue list --repo cadrianmae/gencast --search "<keywords>"` if the description sounds familiar.
- Do not attach API keys, output dirs containing real podcasts, or other private data to the issue body.
