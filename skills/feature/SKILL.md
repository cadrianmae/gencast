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

## Prerequisites (injected at skill-load)

`gh` CLI authenticated against `cadrianmae/gencast`: !`gh auth status 2>&1 | grep -E "Logged in|Token" | head -1 || echo "MISSING — run: gh auth login"`

Installed gencast version: !`gencast --version 2>/dev/null || echo "(not installed — request still works but no installed-version context)"`

Available `component:*` labels on the repo (pick one for the request):

```!
gh label list --repo cadrianmae/gencast --search "component:" --json name --jq '.[].name' 2>/dev/null | sed 's/^/  - /' || echo "  (gh unavailable — skip the component label and let the user add later)"
```

Open enhancements (avoid filing duplicates):

```!
gh issue list --repo cadrianmae/gencast --label enhancement --state open --limit 20 --json number,title --jq '.[] | "  - #\(.number) \(.title)"' 2>/dev/null || echo "  (gh unavailable — skip duplicate check)"
```

## Workflow

1. Ask 1–2 clarifying questions if the request is unclear:
   - What problem does this solve? (the *why*, not just the *what*)
   - What's the concrete user-visible change? (CLI flag, profile field, output format, etc.)
2. Check the open-enhancements list above. If something matches, comment on the existing issue instead of filing a new one.
3. Pick a `component:*` label from the injected list. If unsure, ask the user; if still unsure, file without a component label and note it in the body.
4. Compose the issue title and body using the template below. Title format `[<area>] <concise>` works well (matches existing issue style — see #3, #4, #5 for `[slides A]` examples).
5. File with `gh issue create` against `cadrianmae/gencast`. Use the resilient command from the next section so a missing label does not fail the whole filing.
6. Reply with the issue URL and return to the user's prior work.

## Issue creation (resilient — missing labels do not fail)

```bash
url=$(gh issue create \
  --repo cadrianmae/gencast \
  --title "<[area] concise feature title>" \
  --body "<issue body>" \
  --label enhancement \
  --label "<component:name>" 2>&1) || \
url=$(gh issue create \
  --repo cadrianmae/gencast \
  --title "<[area] concise feature title>" \
  --body "<issue body>" \
  --label enhancement)
echo "$url"
```

The fallback drops the component label and retries.

### Body template

```markdown
## Problem
<the *why* — what frustration / gap / opportunity is this addressing?>

## Proposed Solution
<concrete user-visible change. CLI shape, profile field, output format>

## Alternatives Considered
<from clarifying questions, or 'Not specified' if user skipped>

## Component(s)
`<component>` (or "untriaged" if unknown)

## Depends on / stacks with
<other issue numbers if part of a series like [slides A/B/C]>

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
- Do not over-specify implementation details. The request captures the *what + why*; design happens later via brainstorming.
- Do not invent component labels not in the injected list — file without a label and let triage assign one.
- Do not file follow-on issues without referencing the parent (use the "Depends on" section).
