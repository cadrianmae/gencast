---
name: gencast-notebook-init
description: This skill should be used when the user asks to "draft a gencast notebook", "build a podcast notebook for [topic]", "create a notebook.yaml from these sources", or otherwise wants to scaffold a new gencast notebook from candidate source files. Builds the notebook conversationally — picks profiles, writes YAML, optionally previews the outline.
---

# gencast notebook-init

Build a `notebook.yaml` for gencast conversationally from candidate source files. Replaces the friction of remembering `gencast init` flags with a guided dialogue that picks bundled profiles based on source content and emits a valid YAML notebook the user can immediately run.

## Available profiles in this gencast install

The list below is injected at skill-load time from the local `gencast` install:

```!
gencast list-profiles --json | jq -r '.[] | "- **\(.kind)/\(.name)**: \(.description // "(no description)")"' || echo "(gencast not installed or list-profiles failed — install with: pip install gencast>=1.2.0)"
```

## Prerequisites

- `gencast>=1.2.0` on `PATH`. Verify with: !`gencast --version 2>/dev/null | python3 -c "import sys,re; v=sys.stdin.read().strip(); m=re.search(r'(\d+)\.(\d+)', v); sys.exit(1) if not v else print(v if m and (int(m[1]),int(m[2]))>=(1,2) else f'TOO OLD: need gencast>=1.2.0, found {v} — run: pipx upgrade gencast')" 2>/dev/null || echo "MISSING — install with: pipx install gencast"`
- A directory containing the candidate source files the user named.

If the version check above prints `MISSING`, stop and tell the user to install gencast.

## Workflow

1. **Identify sources.** Read the user's named source paths. Confirm each file exists. If a directory was named, list the files inside it that look like sources (`.md`, `.txt`, `.pdf`).

2. **Suggest profiles.** From the catalogue above, pick a `speaker` / `episode` / `room` triple that fits the source character:
   - Lecture notes / textbook chapters → `revision-duo` + `exam-revision` + `small-room`
   - Interview transcripts → `interview-duo` + `interview` + `small-room`
   - Casual blog posts → `educational-duo` + `casual-discussion` + `small-room`
   - Solo author voice → `solo-tutor` + `concept-explainer` + `vocal-booth`

   Show the user the picked triple and ask for confirmation or override before writing anything.

3. **Scaffold the notebook.** Run `gencast init --minimal --out NB.yaml` (the user picks the path). The wizard writes a skeleton YAML — that is fine; the next step rewrites it with chosen values.

4. **Patch the YAML.** Edit `NB.yaml` to set:
   - `title:` from the source content
   - `sources:` listing the user's source paths (relative to the notebook file)
   - `speaker_profile:`, `episode_profile:`, `room_profile:` from the picked triple
   - `output.formats:` defaulting to `[m4a, transcript, cost]`
   - `briefing_suffix:` if the user wants any specific framing

5. **Optional preview.** Offer to run `gencast preview NB.yaml` to show the outline (no audio yet, ~$0.01 cost). Useful for catching profile mismatches before a full run.

6. **Optional cost estimate.** Offer to run `gencast estimate NB.yaml` to predict cost before generating. Tell the user this is preflight only — no API calls, just heuristic cost projection from token counts.

## What to NOT do

- Do not edit profile YAMLs in `gencast/profiles/bundled/` — the user has their own profile cascade in `./gencast/profiles/` or `~/.config/gencast/profiles/` for overrides.
- Do not run `gencast generate` automatically. The user explicitly opts in to the full run after reviewing the notebook.
- Do not invent profile names. Stick to the catalogue above.
