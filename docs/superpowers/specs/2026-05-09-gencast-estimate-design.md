# gencast estimate — design spec

**Status:** approved (brainstormed 2026-05-09)
**Target version:** gencast v1.1.0
**Owner:** cadrianmae

## Goal

Add `gencast estimate <NB.yaml>` — a preflight cost prediction subcommand that
prints a per-stage USD breakdown for a notebook *without* running the
pipeline, so users can decide whether a notebook is worth $0.20 or $5
before committing to generation.

## Motivation

v1.0 already prints actual costs in `cost.json` after a run. But the
common question — *"is this notebook going to cost me 20¢ or 5 dollars?"*
— has no answer until you've already spent the money. Estimation closes
that loop and unlocks a downstream Claude Code skill (`source-check`) in
v1.2.

## Non-goals

- **Exact prediction.** Output-token counts cannot be known in advance;
  estimation is heuristic with an explicit ±25% caveat.
- **Per-segment optimisation suggestions.** "Drop segment 4" is out of
  scope; we only suggest cheaper *model* alternatives.
- **Calibration runs** (i.e. spend $0.01 on a one-segment outline to
  measure rates): defeats the purpose of "preflight without spending".
- **TTS voice cost variation across providers.** v1.1 hardcodes the
  current OpenAI / Speaches rates from `pyproject` model-budget table.

## User experience

### Default (human-readable)

```
$ gencast estimate my-lecture.yaml

gencast estimate — my-lecture.yaml
================================================================
Source:    1 file  · 12,840 tokens  · "lecture-week-9.md"

Stage breakdown                                       est. USD
----------------------------------------------------  --------
Extract                                                  $0.00
Outline      claude-haiku-4-5         · 13.0k in        $0.04
Transcript   claude-sonnet-4-5        · 6 segs/~9.0k    $0.18
TTS          openai/tts-1-hd          · ~7,200 chars    $0.11
Whisper      whisper-1                · ~6.5 min        $0.04
                                                      --------
                                              Total:    $0.37
                                                      ±25%

Cheaper alternatives
  outline      claude-haiku-4-5      → already cheapest
  transcript   claude-sonnet-4-5     → claude-haiku-4-5    saves ~$0.13 (-72%)
                                       (quality trade-off — see docs)
```

### Machine-readable (`--json`)

```json
{
  "notebook": "my-lecture.yaml",
  "source_tokens": 12840,
  "stages": {
    "extract":   {"provider": null, "model": null, "usd": 0.00},
    "outline":   {"provider": "anthropic", "model": "claude-haiku-4-5",
                  "input_tokens": 13050, "output_tokens": 600, "usd": 0.04},
    "transcript":{"provider": "anthropic", "model": "claude-sonnet-4-5",
                  "input_tokens": 13050, "output_tokens": 8910, "usd": 0.18},
    "tts":       {"provider": "openai",    "model": "tts-1-hd",
                  "characters": 7200, "usd": 0.11},
    "whisper":   {"provider": "openai",    "model": "whisper-1",
                  "duration_minutes": 6.5, "usd": 0.04}
  },
  "total_usd": 0.37,
  "uncertainty_pct": 25,
  "suggestions": [
    {"stage": "transcript", "current": "anthropic/claude-sonnet-4-5",
     "alternative": "anthropic/claude-haiku-4-5",
     "saves_usd": 0.13, "saves_pct": 72, "trade_off": "quality"}
  ]
}
```

### Flags

```
gencast estimate NB.yaml [--json] [--no-suggestions]
```

- `--json` — emit JSON to stdout, suppress human table
- `--no-suggestions` — skip cheaper-alternative suggestion block

## Architecture

Three layers, matching the rest of the codebase:

### Data layer (`gencast/pipeline/estimate.py`, new)

Pure functions, no I/O beyond reading the source file (which already
exists in `gencast/pipeline/extract.py`).

```python
@dataclass(frozen=True)
class StageEstimate:
    stage: Literal["extract", "outline", "transcript", "tts", "whisper"]
    provider: str | None
    model: str | None
    input_tokens: int = 0      # only meaningful for outline/transcript
    output_tokens: int = 0
    characters: int = 0        # only meaningful for tts
    duration_minutes: float = 0.0  # only meaningful for whisper
    usd: float = 0.0


@dataclass(frozen=True)
class Suggestion:
    stage: str
    current: str               # "provider/model"
    alternative: str
    saves_usd: float
    saves_pct: int
    trade_off: str             # short label like "quality" or "speed"


@dataclass(frozen=True)
class Estimate:
    notebook_path: Path
    source_tokens: int
    stages: list[StageEstimate]
    total_usd: float
    uncertainty_pct: int = 25
    suggestions: list[Suggestion] = field(default_factory=list)


def estimate_notebook(nb: Notebook) -> Estimate: ...
```

### Heuristics (`gencast/pipeline/estimate.py`, same file)

Heuristic constants live next to `estimate_notebook` so they're easy to
inspect and tune. Source documents the *why* of each constant.

| Constant | Value | Source |
|---|---|---|
| `OUTLINE_OUTPUT_TOKENS` | 600 | observed across 12 v1.0 runs (mean 580, std 90) |
| `WORDS_PER_SEGMENT` | 150 | per-segment plan target in `prompts/transcript.jinja` |
| `TOKENS_PER_WORD` | 1.5 | tiktoken cl100k empirical for English prose |
| `CHARS_PER_TRANSCRIPT_TOKEN` | 4 | tiktoken inverse heuristic |
| `WORDS_PER_MINUTE` | 150 | conversational TTS pace |
| `OPENAI_TTS_HD_PER_1K_CHARS` | $0.030 | published OpenAI rate |
| `OPENAI_TTS_STD_PER_1K_CHARS` | $0.015 | published OpenAI rate |
| `OPENAI_WHISPER_PER_MINUTE` | $0.006 | published OpenAI rate |

LLM rates are read from the existing `_MODEL_BUDGETS` table in
`gencast/llm/__init__.py` so a single source of truth for input/output
token pricing is preserved.

Local providers (Ollama, Speaches) are hardcoded to $0.00 with a budget
entry shipped alongside v1.3.

### Cheaper-model suggestion logic

A small static downgrade map at the top of `estimate.py`:

```python
DOWNGRADES: dict[str, tuple[str, str]] = {
    # current_model: (alternative_model, trade_off_label)
    "anthropic/claude-sonnet-4-5":  ("anthropic/claude-haiku-4-5",  "quality"),
    "anthropic/claude-opus-4-7":    ("anthropic/claude-sonnet-4-5", "quality"),
    "openai/gpt-5":                 ("openai/gpt-5-mini",           "quality"),
    "openai/gpt-5-mini":            ("openai/gpt-4o-mini",          "quality"),
    "openai/gpt-4o":                ("openai/gpt-4o-mini",          "quality"),
}
```

For each `outline` and `transcript` stage, look up the current
provider/model; if it has an entry, compute the alternative cost; if it
saves >10%, emit a `Suggestion`. Below 10% isn't worth the prompt-quality
trade-off.

### Interface layer (`gencast/cli/main.py`)

New `gencast estimate` Click command. Imports `Notebook.load`,
`estimate_notebook`, and two formatters from a new sibling module:

- `gencast/cli/estimate_formatter.py` — `format_table(est: Estimate) -> str`
  and `format_json(est: Estimate) -> str`. Pure formatters, no I/O.

The CLI command is ~15 lines: load notebook, call `estimate_notebook`,
dispatch to the right formatter, print.

## Edge cases

- **Source token count differs between providers.** v1.0's preflight uses
  tiktoken `cl100k_base` regardless of model. We do the same — accept the
  ±25% bucket absorbs the inter-tokenizer variance (Anthropic is ~10%
  more tokens for the same text in practice).
- **Notebook has zero sources.** Print `Source: empty` and a total of
  $0.00 with a friendly message; don't crash.
- **Provider not in `_MODEL_BUDGETS`.** Print `???` for that stage's USD,
  keep total computable from the rest, don't crash. Add a warning line:
  `! unknown rate for <provider>/<model> — total is a lower bound`.
- **Notebook loads but extracts fail (file not found).** Reuse existing
  `extract_sources` exception path; emit a clean error to stderr.

## Testing strategy

### Unit tests (`tests/unit/test_estimate.py`)

- `test_estimate_known_notebook` — construct a `Notebook` with the
  bundled `exam-revision` episode and a 1k-token fixture file; assert
  `Estimate.total_usd` falls in a known range (use math, not fixtures —
  the exact value is implementation-dependent on rate constants).
- `test_zero_sources` — empty source list produces $0.00 with no crash.
- `test_unknown_model` — provider not in budget table emits `?` USD and
  warning.
- `test_downgrade_suggestion_emitted` — Sonnet → Haiku saves >10%, so
  suggestion is present.
- `test_no_downgrade_when_already_cheapest` — Haiku doesn't suggest
  alternative.

### Component test (`tests/component/test_cli_estimate.py`)

- `test_cli_estimate_table` — invoke `gencast estimate fixtures/notebooks/smoke.yaml`,
  assert stdout contains `Total:` and `±25%` and a dollar amount.
- `test_cli_estimate_json` — `--json` produces valid JSON parseable by
  `json.loads`, with the expected keys.
- `test_cli_estimate_no_suggestions` — `--no-suggestions` omits the
  suggestion block from human output.

### Calibration test (env-gated, optional)

`tests/integration/test_estimate_accuracy.py`:
- Run `estimate` on the smoke notebook; record `total_usd_predicted`.
- Run `gencast generate` on the same notebook; record `total_usd_actual`.
- Assert `abs(predicted - actual) / actual < 0.30` (looser than the
  printed ±25% to absorb run-to-run variance).
- Gated on `GENCAST_TEST_E2E=1` (same env flag as the existing E2E
  smoke).

## Out of scope (future work)

- Suggesting "use map-reduce" for oversized sources (preflight already
  decides this; estimate could surface "your source will be summarised
  before outline → estimate is for compressed token count").
- Estimating with a `--cache-llm-hit-rate 80` flag to model warm caches.
- Localised currency display (always USD).

## Implementation order

Single plan with ~6-8 tasks; small enough that subagent-driven dev can
ship in one wave. Sequencing inside the plan:

1. New `gencast/pipeline/estimate.py` data structures + `estimate_notebook`
2. Heuristics + `_MODEL_BUDGETS` lookup integration
3. Downgrade map + `Suggestion` emission
4. New `gencast/cli/estimate_formatter.py` table + JSON formatters
5. New `gencast estimate` Click command
6. Tests (unit + component)
7. Optional calibration test (env-gated)
8. README update — add `gencast estimate` to CLI reference + a short example

## Acceptance criteria

- `gencast estimate <NB.yaml>` prints a table with all five stage rows + total + ±25% caveat
- `--json` produces machine-parseable output with the documented schema
- Cheaper-model suggestions appear when a downgrade saves >10% on a stage
- All new tests pass; existing v1.0 tests unaffected
- README has a "Cost preview" section under the CLI reference
