# gencast Claude Code skills bundle — design spec

**Status:** approved (brainstormed 2026-05-09)
**Target version:** gencast v1.2.0
**Owner:** cadrianmae
**Depends on:** v1.1.0 (`gencast estimate` ships first)

## Goal

Ship four Claude Code skills bundled with the gencast repo so Claude
Code users can drive notebook creation, preflight checks, and post-run
review through natural-language prompts instead of remembering CLI
flags. Skills shell out to the existing `gencast` CLI — they're thin
workflow recipes, not duplicated logic.

## Motivation

gencast's CLI is full-featured but discovering and remembering all the
subcommands (`generate`, `preview`, `init`, `estimate`, `subtitle`,
`cache`, `list-profiles`) is friction for users who live inside Claude
Code. A skill makes the workflow conversational: *"draft a notebook
from these PDFs"* instead of *"`gencast init --copy ... --out ...`"*.

For Mae specifically, this aligns with the broader ND-friendly UX goal
— minimise decision points, keep cognitive load low, lean on
conversational interfaces over flag spelunking.

## Non-goals

- **Replacing the CLI.** The CLI must remain the source of truth and
  fully usable without Claude Code or any plugin layer.
- **Auto-regenerating segments.** `review-transcript` flags issues but
  does not regenerate audio segments in v1.2 — that needs a new
  `gencast generate --segments X,Y` flag, which is its own future-work
  item.
- **A web UI.** Skills are conversational + CLI; no browser surface.
- **Standalone skills (no gencast required).** Skills shell out to
  gencast. Skill = recipe; CLI = engine.

## Skills shipped (4)

### 1. `gencast:notebook-init`

**Trigger:** *"draft a gencast notebook from these notes"*, *"build a
podcast notebook for [topic]"*

**What it does:**
1. Reads candidate source paths the user mentions
2. Calls `gencast list-profiles` to enumerate bundled options
3. Asks the user 3-5 prompts (matching the `gencast init` wizard's
   structure but conversational, not Click prompts)
4. Suggests speaker / episode / room profiles based on source character
5. Calls `gencast init --out NB.yaml --minimal` then patches the YAML
   directly with the chosen profiles + sources
6. Optionally calls `gencast preview NB.yaml` to show the generated
   outline before the user commits to a full run

**Skill body:** ~80 lines of SKILL.md prompt scaffolding + 1-2 example
flows.

### 2. `gencast:source-check`

**Trigger:** *"are these sources good for a podcast?"*, *"check this
PDF before I generate"*

**What it does:**
1. Token-counts each source via `gencast preview NB.yaml --dry` (no LLM
   calls; just extract + tokenize)
2. Calls `gencast estimate NB.yaml --json` (depends on v1.1) and parses
   the result
3. Reports: total tokens, fits-in-budget verdict, predicted USD cost,
   topical coherence (subjective LLM read), suggestions (split into
   multiple notebooks? summarise first? change to cheaper model?)

**Skill body:** ~60 lines of SKILL.md.

### 3. `gencast:review-transcript`

**Trigger:** *"review this gencast transcript"*, *"is this transcript
good?"*

**What it does:**
1. Reads `transcript.json` from the user-named output directory
2. For each segment, scans the dialogue for issues:
   - awkward phrasings (e.g. *"As an AI..."*, repeated openers)
   - factual claims that contradict source material (if user provides
     source paths)
   - flow problems (jarring topic shifts, missing transitions)
3. Reports a per-segment review with severity tags
4. **Advisory only** — does *not* auto-regenerate. Surfaces what to
   manually fix or which segments to regenerate by hand.

**Skill body:** ~70 lines.

### 4. `gencast:cost-explain`

**Trigger:** *"why did that podcast cost so much?"*, *"explain my
cost.json"*

**What it does:**
1. Reads `cost.json` from a user-named path
2. Per-stage breakdown in plain language: *"Transcript was 60% of cost
   because Sonnet 4.5 is the priciest stage. You ran 8 segments — at 6
   segments it'd have been ~$0.10 cheaper."*
3. Cross-references against `gencast estimate` if the notebook is
   available, showing predicted vs actual delta
4. Suggests optimisations: cheaper outline model, fewer segments, enable
   `--cache-llm`, switch to local-LLM (when v1.3 ships)

**Skill body:** ~70 lines.

## Architecture

### Repo layout (additions)

```
gencast/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest (name, version,
│   │                            # description, skills/)
│   └── README.md                # Plugin overview for marketplace
└── skills/
    ├── notebook-init/
    │   └── SKILL.md
    ├── source-check/
    │   └── SKILL.md
    ├── review-transcript/
    │   └── SKILL.md
    └── cost-explain/
        └── SKILL.md
```

### `plugin.json` shape

```json
{
  "name": "gencast",
  "version": "1.2.0",
  "description": "Conversational interface to gencast — generate, review, and price NotebookLM-style podcasts from documents",
  "author": "cadrianmae",
  "homepage": "https://github.com/cadrianmae/gencast",
  "skills": ["./skills/notebook-init", "./skills/source-check",
             "./skills/review-transcript", "./skills/cost-explain"],
  "requires": {
    "system": ["gencast>=1.1.0", "ffmpeg"]
  }
}
```

The `requires.system.gencast>=1.1.0` is documentation, not enforcement
(Claude Code doesn't currently enforce system deps); the skill SKILL.md
files include a "Prerequisites" section that the assistant checks
before running.

### SKILL.md contract

Each SKILL.md follows the convention from `claude-marketplace`:

1. YAML frontmatter:
   ```yaml
   ---
   name: cost-explain
   description: Explain cost.json from a gencast run in plain language and suggest optimisations.
   ---
   ```
2. **Trigger phrases** section — when this skill should activate
3. **Prerequisites** — `gencast` CLI installed, file paths user must
   provide
4. **Workflow** — numbered steps the assistant follows
5. **Example transcript** — a worked conversation the assistant can
   pattern-match against

### Coupling with gencast CLI

Skills invoke gencast via shell-out — no Python imports, no parsing of
gencast internals. Stable contracts skills rely on:

- `gencast list-profiles --type X --json` — for enumeration
- `gencast init --out PATH [--minimal] [--copy NB]` — for scaffolding
- `gencast preview NB.yaml [--save-outline PATH]` — for outline-only dry
  runs
- `gencast estimate NB.yaml --json` — for cost prediction (v1.1)
- `transcript.json` schema — `{segments: [{speaker, text, ...}], ...}`
- `cost.json` schema — `{stages: [{name, model, usd, ...}], total_usd}`

If any of these shapes change in future gencast versions, the skills
must be updated in lock-step. Plan: add a `tests/skills/` directory
with smoke tests that invoke each skill's CLI calls against the smoke
fixture and assert exit codes / JSON shape — catches breakage at
gencast-side test time, not at user-skill-invocation time.

## Distribution

### Discovery path

Two-tier:

1. **Bundled with `pip install gencast`** — `skills/` and
   `.claude-plugin/` ship in the wheel; `pyproject.toml` adds
   `package-data` entries for `*.md` and `*.json`. Users with the
   plugin path configured can point at the installed location.

2. **Marketplace mirror** — your existing
   `claude-marketplace` repo gets a `plugins/gencast/plugin.json` that
   points to this repo as the source. Users do `/plugin install
   gencast` and Claude Code fetches from GitHub. The release workflow
   triggers a marketplace-mirror update via PR.

### Release workflow update

Extend `.github/workflows/release.yml` to:
1. Build + publish wheel to PyPI (existing)
2. Open a PR against `cadrianmae/claude-marketplace` updating the
   `gencast` plugin entry with the new version + tag SHA. Manual merge
   on the marketplace side.

## Testing strategy

### `tests/skills/test_skill_smoke.py`

For each of the 4 skills, a smoke test that:
1. Invokes the underlying gencast CLI calls listed in the SKILL.md
   workflow against the bundled smoke fixture
2. Asserts each returns the expected schema (e.g. `gencast estimate
   --json` returns valid JSON with the documented keys)
3. Doesn't actually invoke the LLM via Claude Code (skills are tested
   for *contract*, not for AI behaviour — that's manual + ad-hoc)

### `tests/skills/test_plugin_manifest.py`

- Validates `plugin.json` JSON shape against a small Pydantic schema
- Asserts every skill listed in `plugin.json` has a corresponding
  `SKILL.md` on disk
- Asserts each `SKILL.md` has the required frontmatter sections

## Edge cases

- **User invokes a skill without gencast installed.** Skill workflow
  step 1 in each SKILL.md is "verify `gencast --version` runs; if not,
  print install instructions and abort."
- **User invokes `cost-explain` with a non-gencast cost.json.** Skill
  validates the expected schema; if missing keys, prints a clear error.
- **Skill triggers on too-broad phrasing.** Each SKILL.md's trigger
  section is narrow (specific verbs + "gencast" or context clues from
  recent files like `transcript.json`).
- **`review-transcript` on a very long transcript** (50+ segments).
  Skill workflow chunks the review by segment groups of 10 to keep
  responses focused.

## Out of scope (future work)

- `gencast:brief` — helping write a good `default_briefing` for a
  custom episode profile. Possible v1.3+ once usage patterns surface.
- Auto-regenerating audio segments from `review-transcript`. Needs
  `gencast generate --segments X,Y` flag (separate ask).
- Skill-level memory (Claude Code doesn't expose this cleanly yet).

## Implementation order

Single plan, ~10-12 tasks (4 skills × 2 files each + plugin manifest +
tests + release workflow update + README). Sequencing:

1. `plugin.json` + skills/ directory scaffolding + `package-data` in
   pyproject
2. `notebook-init/SKILL.md`
3. `source-check/SKILL.md` (requires v1.1 estimate already shipped)
4. `review-transcript/SKILL.md`
5. `cost-explain/SKILL.md`
6. `tests/skills/test_plugin_manifest.py`
7. `tests/skills/test_skill_smoke.py`
8. README update — "Claude Code integration" section
9. Marketplace PR (manual or via release workflow extension — defer
   automation to v1.3 if scope creep)

## Acceptance criteria

- All 4 SKILL.md files load via Claude Code's `/plugin install gencast`
- Each skill's documented workflow runs successfully against the smoke
  notebook fixture
- `pip install gencast==1.2.0` puts skills + plugin manifest on disk
  in the right place to be pickable up by Claude Code
- `tests/skills/` is green
- README shows the 4 trigger phrases in a table under "Claude Code
  integration"
