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

## Prerequisites (injected at skill-load)

`gh` CLI authenticated against `cadrianmae/gencast`: !`gh auth status 2>&1 | grep -E "Logged in|Token" | head -1 || echo "MISSING — run: gh auth login"`

Installed gencast version: !`gencast --version 2>/dev/null || echo "(not installed — bug-report still works but version field will be 'unknown')"`

Available `component:*` labels on the repo (pick one for the issue):

```!
gh label list --repo cadrianmae/gencast --search "component:" --json name --jq '.[].name' 2>/dev/null | sed 's/^/  - /' || echo "  (gh unavailable — skip the component label and let the user add later)"
```

## Workflow

1. Ask 1–2 clarifying questions if the description is unclear:
   - What were the steps to reproduce?
   - What was expected vs what actually happened?
2. Pick a `component:*` label from the list above. Match the bug to the component most directly responsible. If unsure, ask the user; if still unsure, file without a component label and note it in the body for triage.
3. Capture the installed gencast version (the prereq check above).
4. Compose the issue title and body using the template below.
5. File with `gh issue create` against `cadrianmae/gencast`. Use the resilient command from the next section so a missing label does not fail the whole filing.
6. Reply with the issue URL and return to the user's prior work.

## Issue creation (resilient — missing labels do not fail)

```bash
url=$(gh issue create \
  --repo cadrianmae/gencast \
  --title "<concise bug title>" \
  --body "<issue body>" \
  --label bug \
  --label "<component:name>" 2>&1) || \
url=$(gh issue create \
  --repo cadrianmae/gencast \
  --title "<concise bug title>" \
  --body "<issue body>" \
  --label bug)
echo "$url"
```

The fallback drops the component label and retries; the version field stays in the body's Environment section so version context never gets lost.

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
Component: `<component>` (or "untriaged" if unknown)
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
- Do not invent component labels not in the injected list — file without a label and let triage assign one.
