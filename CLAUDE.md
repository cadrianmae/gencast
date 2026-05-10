# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**gencast** is a Python CLI that generates conversational podcasts from documents — a cost-effective, customisable, local-first alternative to NotebookLM. Input is a `notebook.yaml` describing the source files + chosen profiles; output is an M4A with embedded SRT subtitles. The project also ships a Claude Code plugin (4 skills) for conversational use inside Claude Code.

User context: created for Mae Capacite (TU Dublin Computer Science FYP) with neurodivergent-friendly UX as a first-class concern.

## Common commands

Always activate the venv before running anything: `source venv/bin/activate`.

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -e .                           # editable install — `gencast` on PATH
pipx install -e .                          # OR system-wide install

# Run the pipeline
gencast init                               # interactive notebook wizard
gencast preview notebook.yaml              # outline-only dry run (~$0.01)
gencast generate notebook.yaml             # full pipeline -> out/<basename>.m4a
gencast estimate notebook.yaml             # cost prediction, no API calls
gencast estimate --rates-only --json       # rate table (used by skills)
gencast list-profiles --json               # bundled profile catalogue
gencast cache stats|clear                  # TTS/LLM cache management

# Tests
PYTHONPATH=. ./venv/bin/pytest --tb=short -q             # full suite (~318 tests)
PYTHONPATH=. ./venv/bin/pytest tests/unit/test_estimate.py -v       # one file
PYTHONPATH=. ./venv/bin/pytest -k "test_name_substring" -v          # by name
GENCAST_TEST_E2E=1 PYTHONPATH=. ./venv/bin/pytest tests/integration/ # spends real money
PYTHONPATH=. ./venv/bin/pytest tests/skills/ -v          # plugin manifest + smoke

# Type checking + lint
basedpyright                               # strict mode, warn-only (errors only on critical issues)
ruff check . && ruff format .
```

API keys — export or let `gencast init` prompt:

```bash
export OPENAI_API_KEY=sk-...        # required (TTS + Whisper)
export ANTHROPIC_API_KEY=sk-ant-... # required (default outline + transcript)
export MISTRAL_API_KEY=...          # optional (better PDF extraction)
```

For local-LLM development, retrieve via `pass api/<provider>` first (per Mae's `feedback_pass_for_api_keys.md` memory).

## Architecture

The v1.0+ rewrite replaces the original single-`gencast.py` script. Three things matter most for new contributors:

### Three-axis profile system (`gencast/profiles/`)

A notebook composes three orthogonal profile types, each in its own bundled YAML directory:

- **Speakers** (`speakers/`): voice + persona pair (e.g. `educational-duo`, `interview-duo`, `solo-tutor`). Each defines `host1`/`host2` with TTS provider/model + style notes.
- **Episodes** (`episodes/`): conversation shape (e.g. `exam-revision`, `casual-discussion`, `interview`, `concept-explainer`). Defines outline structure, transcript briefing, target segment count, etc.
- **Rooms** (`rooms/`): acoustic environment for spatial audio (e.g. `small-room`, `large-room`, `vocal-booth`, `ambient`). Drives Schroeder reverb + ITD parameters.

A notebook picks one of each. `gencast/notebook.py:resolve_notebook(nb)` cascades user → project → bundled overrides and produces a `ResolvedNotebook` dataclass that downstream pipeline stages consume. Bundled profiles ship inside the wheel via `package-data`; the cascade also looks at `./gencast/profiles/` and `~/.config/gencast/profiles/` for user overrides.

### Pipeline stages (`gencast/pipeline/`)

The pipeline is a sequence of pure functions, each consuming the previous stage's output + the resolved notebook:

```
extract → preflight → outline → transcript → audio (TTS + spatial) → subtitles → package
```

Each stage is in its own module, takes a `CostMeter` (always-on cost tracker — see `gencast/cost.py`), and writes a structured artifact (e.g. `outline.json`, `transcript.json`, `cost.json`). The stages are sequential but independently testable. `gencast/pipeline/__init__.py:run_pipeline(nb)` orchestrates them.

Two pipeline-internal subsystems worth knowing:

- **Map-reduce summarisation** (`pipeline/mapreduce.py`): when source tokens exceed the chosen model's input budget (`pipeline/preflight.py:_MODEL_BUDGETS`), gencast recursively summarises before outline. The estimator does NOT account for this — it estimates the uncompressed source path.
- **Estimation** (`pipeline/estimate.py`): preflight cost prediction without running anything. Pure functions only; rates come from `litellm.model_cost` (single source of truth — same dict the runtime cost tracker uses via `response_cost`). Heuristic constants (`OUTLINE_OUTPUT_TOKENS`, `WORDS_PER_SEGMENT`, etc.) live next to the estimator and are documented in `docs/superpowers/specs/2026-05-09-gencast-estimate-design.md`.

### LLM + TTS abstraction layers (`gencast/llm/`, `gencast/tts/`)

- `llm/__init__.py:chat_completion()` is the single LiteLLM call site. All chat traffic flows through here, which records into the `CostMeter` and centralises caching (`llm/cache.py`).
- `tts/` has pluggable backends (`openai.py`, `speaches.py`); `tts/cache.py` is always-on (synthesis is the most expensive cacheable step).

If you add a new model provider, you do NOT need to register it anywhere — LiteLLM resolves the `provider/model` string. The estimator pulls rates from `litellm.model_cost` automatically (see `dump_rates_table` in `pipeline/estimate.py` for the lookup pattern).

### Layered separation

Strictly enforced — pull requests that mix layers get pushed back:

- **Data** (`pipeline/extract.py`, parts of `notebook.py`): pure I/O, returns raw strings/dicts.
- **Business logic** (everything in `pipeline/` + `llm/` + `tts/`): never prints, returns dataclasses.
- **Interface** (`cli/main.py`): Click subcommands, all user-facing strings + error messages live here. Imports from `pipeline/` are deferred (lazy) inside command bodies to keep `gencast --help` fast.

## Claude Code plugin (`.claude-plugin/` + `skills/`)

The same repo doubles as a Claude Code plugin/marketplace. Two manifests:

- `.claude-plugin/marketplace.json` — marketplace listing (one plugin: gencast itself, fetched via HTTPS git URL).
- `.claude-plugin/plugin.json` — the plugin manifest. `author` MUST be the object form `{name, email}`; the string form silently fails Claude Code's schema validation.

Four `SKILL.md` files under `skills/`:

- `notebook-init` — conversational notebook builder (uses `gencast list-profiles` + `gencast init`)
- `source-check` — preflight quality + cost (uses `gencast estimate`)
- `review-transcript` — advisory transcript review (operates on `transcript.json`, no auto-regen in v1.2.x)
- `cost-explain` — cost.json explainer (uses `gencast estimate --rates-only`)

Each SKILL.md uses Claude Code's `` !`command` `` (single-line) and ` ```! ` (multi-line) **dynamic context injection** to bake fresh metadata into the prompt at skill-load time — see https://code.claude.com/docs/en/skills.md#inject-dynamic-context. Frontmatter is third-person ("This skill should be used when..."); body is imperative form. Both are enforced by `tests/skills/test_plugin_manifest.py`.

The skills bundle ships inside the Python wheel via `MANIFEST.in` (which includes `.claude-plugin/` + `recursive-include skills *.md`). Test infrastructure: `tests/skills/conftest.py` prepends `venv/bin` to `PATH` so smoke tests resolve `gencast` to the editable install rather than any system-wide install.

## Release workflow

`.github/workflows/release.yml` fires on tag push (`v*.*.*`):

1. `git tag -a v1.X.Y -m "..."` then `git push origin v1.X.Y`
2. Workflow builds wheel + sdist, validates with twine, publishes to PyPI via OIDC trusted publishing (no API token stored — relies on the pending publisher registered at https://pypi.org/manage/account/publishing/)
3. After PyPI propagation: `gh release create v1.X.Y --title "..." --notes "..."`

Bump `version` in three places before tagging: `pyproject.toml`, `.claude-plugin/plugin.json`, and `.claude-plugin/marketplace.json` (use `gencast>=X.Y.Z` in plugin.json's `requires.system` too).

## Plans + specs

`docs/superpowers/specs/` and `docs/superpowers/plans/` contain the brainstorm specs and TDD implementation plans for v1.1 / v1.2 / v1.2.1. They are the source of truth for design decisions (heuristic constants, downgrade map, plugin layout). When extending a feature, update its spec first.

`docs/future-work.md` is the backlog. v1.3 (local-LLM Ollama) is the next planned minor release.

## Subagent-driven development pattern

For multi-task plans, the controller (you) creates per-task git worktrees branched off the integration branch, dispatches `general-purpose` subagents (model: sonnet) one per task, runs `code-documentation:code-reviewer` after each subagent returns, and merges into the integration branch. Same-file tasks must serialise — appending tasks to one file in parallel produces unavoidable merge conflicts. The pattern is documented by example in `docs/superpowers/plans/2026-05-09-gencast-v1.2-skills.md` (5 waves) and v1.1-estimate (8 waves).

**Critical**: always run merge commands with `git -C <trunk-worktree-path>` or after `cd`-ing into the trunk worktree. Bash tool calls don't persist cwd between invocations — running `git merge` from the main repo cwd silently merges into `main` instead of the integration branch. Same root cause for both v1.0 and v1.1 cutover incidents.

## Editor LSP

The project ships `.claude/settings.json` with `pyright-lsp@claude-plugins-official` enabled. It needs the `pyright` binary on PATH — collaborators install once with `pipx install pyright` (or `pip install pyright` / `npm install -g pyright`). The strict basedpyright lives in the `[dev]` extras and runs in CI / the `gencast-release-prep` skill; pyright-lsp covers the in-editor case.

## Critical reminders

- Tests use `PYTHONPATH=.` — pytest does not auto-discover the package without it.
- `gencast` entry point is `gencast.cli.main:cli` (NOT `gencast:main` — that's the pre-rewrite chain that still trips users with stale `pipx install gencast` from v0.6.x).
- For `gencast estimate` calibration tests: `GENCAST_TEST_E2E=1` spends real money (~$0.20/run); skip otherwise.
- v1.2.1 added a version-gate to skill prereq checks. If you change `gencast --version` output format, update the regex in all four `skills/*/SKILL.md` files (search for `python3 -c "import sys,re`).
- Subtitles use Whisper but they are tagged with `mov_text` codec for M4A muxing — VLC needs Audio → Visualizations enabled to display them on audio-only files.
