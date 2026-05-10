---
name: gencast-feature
description: This skill should be used when the user asks to "file a gencast feature", "request a gencast feature", "log a gencast enhancement", "suggest a gencast improvement", or otherwise wants to track a gencast feature request. Files feature requests as GitHub issues on cadrianmae/gencast.
allowed-tools: Bash, AskUserQuestion
argument-hint: <feature description>
---

# File a gencast feature request

Log a gencast enhancement as a GitHub issue on `cadrianmae/gencast`. For tracking only — do NOT attempt to design or implement the feature in this session.

## Quick example

```
/gencast:feature add --segments X,Y flag to gencast generate so review-transcript can auto-regenerate flagged segments
```

## Prerequisites

- `gh` CLI authenticated against `cadrianmae/gencast`. Verify with: !`gh auth status 2>&1 | grep -E "Logged in|Token" | head -1 || echo "MISSING — run: gh auth login"`
- Installed gencast version (helps determine which release the feature targets): !`gencast --version 2>/dev/null || echo "(not installed — request still works but no installed-version context)"`

## Workflow

1. Ask 1–2 clarifying questions if the request is unclear:
   - What problem does this solve? (the *why*, not just the *what*)
   - What's the concrete user-visible change? (CLI flag, profile field, output format, etc.)
2. Determine which gencast area is affected. Common: `cli`, `pipeline:outline`, `pipeline:transcript`, `pipeline:audio`, `pipeline:estimate`, `tts`, `llm`, `profiles`, `plugin`, `docs`.
3. Check whether this overlaps with anything in `docs/future-work.md` or open issues — if yes, comment on the existing item rather than filing a duplicate.
4. Compose the issue title and body using the template below.
5. File with `gh issue create` against `cadrianmae/gencast` with labels `enhancement` + `component:<name>` + (optional) `target:v1.X` if the user has a specific release in mind.
6. Reply with the issue URL and return to the user's prior work.

## Issue creation

```bash
gh issue create \
  --repo cadrianmae/gencast \
  --title "<concise feature title>" \
  --body "<issue body>" \
  --label enhancement \
  --label "component:<name>"
```

### Body template

```markdown
## Problem
<the *why* — what frustration / gap / opportunity is this addressing?>

## Proposed Solution
<concrete user-visible change. CLI shape, profile field, output format>

## Alternatives Considered
<from clarifying questions, or 'Not specified' if user skipped>

## Component(s)
`<component>`

---
Suggested by: <user> on <YYYY-MM-DD>
gencast version installed: `<x.y.z>`
```

## After filing

Respond with the issue URL, e.g.:

> "gencast feature request filed: https://github.com/cadrianmae/gencast/issues/43. Continuing with your current work."

Then return focus to whatever the user was doing before this command.

## What to NOT do

- Do not design or scope the feature in the same session — this skill is for capturing the idea while it's fresh.
- Do not file duplicates: check `docs/future-work.md` AND `gh issue list --repo cadrianmae/gencast --label enhancement --search "<keywords>"` first.
- Do not over-specify implementation details. The request captures the *what + why*; design happens later via brainstorming.
