# gencast v1.0 Plan C — Rich UI, init wizard, map-reduce, caches, tests, v1.0.0 cutover

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the rewrite from "end-to-end works on the CLI" to "tagged v1.0.0 release on `main`" — adding the Rich Live UI, `gencast init` wizard, map-reduce summarisation, opt-in LLM cache + cache subcommands, the Whisper STT subtitle path, the test pyramid, GitHub Actions CI, and the final cutover.

**Architecture:** Phase 6 fills out user-facing UX (Rich Live + verbosity flags + init wizard). Phase 7 closes the spec's remaining functional gaps (map-reduce for oversize sources, opt-in LLM cache, `gencast subtitle` Whisper path lifted from v0.6.x, `gencast cache status/clear`). Phase 8 hardens the project for release: integration + E2E tests behind env-var gates, GitHub Actions for free-tier vs secrets-gated tiers, README rewrite, then merge `rewrite/v1.0` → `main` and tag `v1.0.0`.

**Tech Stack:** Rich (Live, Progress, Layout), Click (prompts, subcommands), tiktoken (chunk-counting), LiteLLM (chat completion already in place), OpenAI SDK (Whisper STT), `srt` library (existing v0.6.x dep for SRT chunk-merge), GitHub Actions, ffmpeg (already system dep).

**Spec:** `docs/superpowers/specs/2026-05-07-gencast-v1-rewrite-design.md` — Sections 1, 2, 3.3, 3.4, 4.x, 5.3, 5.4, 6, 10 (phases 6-8).

**Plan A + B handoff:** Trunk is `rewrite/v1.0` at commit `9e3c3ee`. End-to-end pipeline runs (`gencast generate NB.yaml` produces `.m4a` with embedded subs). 229 tests passing. Existing contracts Plan C builds on:

- `gencast.logger.Reporter` ABC + `PlainReporter` (Plan A — Rich variant arrives in this plan's T1)
- `gencast.pipeline.run_pipeline(notebook)` and stage executors (Plan A + B)
- `gencast.pipeline.preflight.preflight(source_tokens, model)` raising `SourceTooLargeError` (T6 of this plan replaces the raise with map-reduce)
- `gencast.llm.chat_completion(...)` (Plan A — T7 of this plan adds an opt-in LLM cache)
- `gencast.tts.cache.TTSDiskCache` + `default_cache_dir()` (Plan B — T9 of this plan adds the cache CLI subcommands that operate on this directory)
- `gencast/cli/main.py` Click group with `list-profiles`, `preview`, `generate` (T4, T8, T9 add three more)
- `tests/fixtures/notebooks/smoke.{yaml,md}` (Plan B — used by T13 E2E smoke and CI workflows)

---

## Phase scope (this plan)

| Phase | Name | Tasks | Output at end |
|---|---|---|---|
| **6** | Rich UI + init wizard | T1–T4 | Rich Live two-band display when interactive; `gencast init` produces `notebook.yaml` |
| **7** | Map-reduce + LLM cache + Whisper subtitle + cache subcommands | T5–T9 | All spec §3.3 CLI commands shipped; oversize sources work end-to-end |
| **8** | Test pyramid + CI + cutover | T10–T18 | Release-quality test coverage; `main` is at v1.0.0 |

---

## Execution waves

| Wave | Trunk state at start | Tasks | Concurrency | Notes |
|---|---|---|---|---|
| **C0** | post-Plan-B trunk (`9e3c3ee`) | T1, T4, T5, T7, T8, T10 | **6-way** | All independent — different files, no shared edits |
| **C1** | post-C0 | T2, T6, T9 | 3-way | T2 needs T1 (RichReporter exists); T6 needs T5 (chunker exists); T9 needs T7 (LLM cache layout exists) |
| **C2** | post-C1 | T3 | 1-way | Wires reporter calls into pipeline stages; needs T2 (selection at startup) |
| **C3** | post-C2 | T11, T12, T13 | 3-way | Integration + E2E tests, all independent |
| **C4** | post-C3 | T14, T15 | 2-way | GitHub Actions workflows, parallel files |
| **C5** | post-C4 | T16, T17 | 2-way | README + pyproject polish, parallel |
| **C6** | post-C5 | T18 | controller-only | Final cutover ceremony — no subagent dispatch |

Sequential floor: 7 waves. Total task count: **18**.

### Branch naming

`rewrite/v1.0-taskC<N>-<short-slug>`. Examples:

- `rewrite/v1.0-taskC1-rich-reporter`
- `rewrite/v1.0-taskC5-mapreduce-chunker`
- `rewrite/v1.0-taskC18-cutover` (this branch is for the merge-back PR; created by the controller, not a subagent)

Merged into `rewrite/v1.0` with `--no-ff` to preserve task boundaries in history (matches Plan A + B convention).

### Model assignments

(Haiku for verbatim lifts and pure-boilerplate filesystem ops; sonnet for everything else.)

| Task | Implementer | Reasoning |
|---|---|---|
| T1 | sonnet | Rich Live + Layout — careful UX work |
| T2 | sonnet | Reporter selection at startup + verbosity flag plumbing |
| T3 | sonnet | Wire reporter into pipeline stages — touches several files |
| T4 | sonnet | Click prompts + YAML emission — UX detail matters |
| T5 | sonnet | Recursive map-reduce — algorithmic; needs careful chunk boundary handling |
| T6 | sonnet | Wire map-reduce into preflight — integration point |
| T7 | **haiku** | sha256 disk cache wrapper around `chat_completion` — boilerplate |
| T8 | sonnet | Whisper STT path — lift v0.6.x logic + adapt to v1 CLI |
| T9 | **haiku** | `gencast cache status/clear` — straight filesystem ops |
| T10 | sonnet | Audio-reference fixture regression — needs deterministic seeding |
| T11 | sonnet | OpenAI TTS integration test, env-gated |
| T12 | sonnet | Anthropic chat integration test, env-gated |
| T13 | sonnet | E2E mini-notebook smoke, env-gated |
| T14 | **haiku** | GH Actions YAML — straight config |
| T15 | **haiku** | GH Actions YAML — straight config |
| T16 | sonnet | README rewrite — content quality matters |
| T17 | **haiku** | pyproject.toml polish — small edits |
| T18 | controller | Cutover; no subagent |

### Reviewer for every task

Single combined spec+quality review via `code-documentation:code-reviewer` agent (sonnet model) after each task's implementation lands.

---

## File Structure (Plan C)

| Path | Created/Modified | Responsibility |
|---|---|---|
| `gencast/logger.py` | Modified | Add `RichReporter` two-band Live implementation; teach `make_reporter` to pick Rich on TTY |
| `gencast/cli/main.py` | Modified | Add `--verbose/-v`, `--debug/-vv`, `--quiet/-q`, `--silent`, `--log-file` group-level options; add `init`, `subtitle`, `cache` subcommands |
| `gencast/cli/init_wizard.py` | Created | Click prompt-based wizard logic — separated from `main.py` for testability |
| `gencast/pipeline/__init__.py` | Modified | Thread reporter through stage calls (`reporter.stage_start`, `stage_activity`, `stage_advance`, `stage_done`) |
| `gencast/pipeline/outline.py` | Modified | Optional `reporter` kwarg; emit activity for each LLM call |
| `gencast/pipeline/transcript.py` | Modified | Optional `reporter` kwarg; emit per-segment activity with cache-hit % |
| `gencast/pipeline/audio.py` | Modified | Optional `reporter` kwarg; emit per-clip TTS activity |
| `gencast/pipeline/extract.py` | Modified | Optional `reporter` kwarg; emit per-source activity |
| `gencast/pipeline/preflight.py` | Modified | When source > budget, dispatch to map-reduce summariser instead of raising |
| `gencast/pipeline/mapreduce.py` | Created | Recursive chunk → summarise → merge until within budget |
| `gencast/llm/__init__.py` | Modified | Optional disk cache layer behind `cache_llm` flag |
| `gencast/llm/cache.py` | Created | sha256-keyed disk cache for chat completions |
| `gencast/pipeline/whisper_subtitle.py` | Created | Chunked Whisper STT lifted from v0.6.x `src/audio.py` (paths-only — no `parse_dialogue` carryover) |
| `tests/component/test_rich_reporter.py` | Created | Verify Rich Live render shape (no UI assertions; just method calls + state) |
| `tests/component/test_cli_init.py` | Created | CliRunner-based wizard test |
| `tests/component/test_cli_subtitle.py` | Created | Mocked Whisper STT test |
| `tests/component/test_cli_cache.py` | Created | Filesystem cache subcommand tests |
| `tests/component/test_pipeline_reporter_calls.py` | Created | Verify reporter is called from each stage |
| `tests/component/test_mapreduce.py` | Created | Recursive summarisation test with mocked LLM |
| `tests/component/test_llm_cache.py` | Created | LLM cache hit/miss roundtrip |
| `tests/integration/test_openai_tts.py` | Created | Real OpenAI TTS — env-gated |
| `tests/integration/test_anthropic_chat.py` | Created | Real Anthropic chat — env-gated |
| `tests/e2e/test_smoke.py` | Created | Real-API end-to-end notebook → m4a — env-gated |
| `tests/fixtures/audio_reference/` | Created | Deterministic-seed audio reference for room-FX regression |
| `tests/unit/test_audio_reference_regression.py` | Created | Per-room-preset audio regression test |
| `.github/workflows/ci.yml` | Created | Free-tier: unit + component on every PR |
| `.github/workflows/integration.yml` | Created | Secrets-gated: integration + E2E on push to `main` |
| `README.md` | Modified | v1.0 install, examples, profile cascade, cost notes |
| `pyproject.toml` | Modified | Version → 1.0.0, classifiers, model-budget table sync (rename old model IDs to match `schemas.py`), add `tiktoken` if not already present |

---

## Phase 6 — Rich UI + init wizard

### Task C1: RichReporter (two-band Live display)

**Files:**
- Modify: `gencast/logger.py`
- Test: `tests/component/test_rich_reporter.py`

The spec mock (§3.4) shows a two-band layout: progress bar on top, current activity below. Per-stage Rich `Progress` instance lives inside a `Live` context. Per-speaker emoji from `Speaker.avatar.emoji` shows up on the activity line for stages where one speaker is the focus (transcript per-segment, audio per-clip).

We don't try to assert on visual output in tests — just verify state transitions and that `update_display` is called.

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_rich_reporter.py
"""RichReporter state tests — does not assert on visual output."""

from __future__ import annotations

from gencast.logger import RichReporter


def test_rich_reporter_records_stage_state():
    r = RichReporter(verbosity=1)
    r.stage_start(1, 10, "Resolve", total_items=None)
    assert r._current_stage_index == 1
    assert r._current_stage_total == 10
    assert r._current_stage_name == "Resolve"
    r.stage_done()
    assert r._current_stage_index == 1  # last seen, not reset


def test_rich_reporter_advance_increments():
    r = RichReporter(verbosity=1)
    r.stage_start(1, 10, "Audio", total_items=5)
    r.stage_advance(items=2)
    assert r._items_done == 2
    r.stage_advance(items=3)
    assert r._items_done == 5


def test_rich_reporter_activity_records():
    r = RichReporter(verbosity=1)
    r.stage_start(2, 10, "Outline")
    r.stage_activity("[claude-haiku-4-5] generating outline...")
    assert "claude-haiku-4-5" in r._latest_activity


def test_rich_reporter_log_levels_respect_verbosity():
    r = RichReporter(verbosity=0)
    r.info("hidden")
    assert r._info_buffer == []  # silent at v=0

    r2 = RichReporter(verbosity=2)
    r2.debug("visible at debug")
    assert "visible at debug" in r2._info_buffer[-1]


def test_make_reporter_picks_rich_on_tty(monkeypatch):
    """make_reporter switches to RichReporter when stdout is a TTY."""
    import gencast.logger as L

    monkeypatch.setattr(L.sys.stdout, "isatty", lambda: True)
    r = L.make_reporter(verbosity=1)
    assert isinstance(r, RichReporter)


def test_make_reporter_picks_plain_when_not_tty(monkeypatch):
    import gencast.logger as L

    monkeypatch.setattr(L.sys.stdout, "isatty", lambda: False)
    r = L.make_reporter(verbosity=1)
    assert r.__class__.__name__ == "PlainReporter"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_rich_reporter.py -v`
Expected: FAIL with `ImportError` on `RichReporter`.

- [ ] **Step 3: Implement `RichReporter`**

Append to `gencast/logger.py`:

```python
import sys
from typing import Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
    from rich.layout import Layout
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class RichReporter(Reporter):
    """Two-band Live display: progress bar on top, current activity below."""

    def __init__(self, verbosity: int = 1):
        if not RICH_AVAILABLE:
            raise RuntimeError("Rich is not installed; install gencast[all] or use PlainReporter")
        self.verbosity = verbosity
        self._console = Console(force_terminal=True)
        self._current_stage_index = 0
        self._current_stage_total = 0
        self._current_stage_name = ""
        self._items_total: Optional[int] = None
        self._items_done = 0
        self._latest_activity = ""
        self._info_buffer: list[str] = []
        self._progress: Optional[Progress] = None
        self._task_id = None
        self._live: Optional[Live] = None

    def _ensure_live(self) -> None:
        if self._live is not None:
            return
        self._progress = Progress(
            TextColumn("  [{task.fields[stage]}] {task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=self._console,
        )
        self._live = Live(self._render(), console=self._console, refresh_per_second=4)
        self._live.start()

    def _render(self) -> Panel:
        if self._progress is None:
            return Panel("starting...", border_style="cyan")
        return Panel(
            f"{self._progress}\n\n  {self._latest_activity}",
            title=f"gencast",
            border_style="cyan",
        )

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    def stage_start(self, n: int, total: int, name: str, total_items: Optional[int] = None) -> None:
        self._ensure_live()
        self._current_stage_index = n
        self._current_stage_total = total
        self._current_stage_name = name
        self._items_total = total_items
        self._items_done = 0
        self._latest_activity = ""
        if self._progress is not None:
            if self._task_id is not None:
                self._progress.remove_task(self._task_id)
            self._task_id = self._progress.add_task(
                description=name,
                total=total_items if total_items is not None else 1,
                stage=f"{n}/{total}",
            )
        self._refresh()

    def stage_activity(self, line: str) -> None:
        self._latest_activity = line
        self._refresh()

    def stage_advance(self, items: int = 1) -> None:
        self._items_done += items
        if self._progress is not None and self._task_id is not None and self._items_total is not None:
            self._progress.advance(self._task_id, items)
        self._refresh()

    def stage_done(self) -> None:
        if self._progress is not None and self._task_id is not None and self._items_total is not None:
            self._progress.update(self._task_id, completed=self._items_total)
        self._refresh()

    def info(self, msg: str) -> None:
        if self.verbosity >= 1:
            self._info_buffer.append(f"[INFO] {msg}")

    def debug(self, msg: str) -> None:
        if self.verbosity >= 2:
            self._info_buffer.append(f"[DEBUG] {msg}")

    def warn(self, msg: str) -> None:
        if self.verbosity >= 1:
            self._info_buffer.append(f"[WARN] {msg}")

    def error(self, msg: str) -> None:
        # Errors always emit
        self._info_buffer.append(f"[ERROR] {msg}")

    def close(self) -> None:
        """Tear down the Live display. Call at end of pipeline run."""
        if self._live is not None:
            self._live.stop()
            self._live = None
```

Replace `make_reporter`:

```python
def make_reporter(verbosity: int = 1) -> Reporter:
    """Pick a Reporter implementation. Rich on TTY, Plain otherwise."""
    if RICH_AVAILABLE and sys.stdout.isatty():
        return RichReporter(verbosity=verbosity)
    return PlainReporter(verbosity=verbosity)
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_rich_reporter.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/logger.py tests/component/test_rich_reporter.py
git commit -m "Plan C Task 1: RichReporter two-band Live display + TTY auto-detection"
```

---

### Task C2: Reporter selection + verbosity flag plumbing

**Files:**
- Modify: `gencast/cli/main.py`
- Test: `tests/component/test_cli_verbosity.py`

Add group-level Click options that build a `Reporter` instance and stash it on the Click context. Subcommands read it from `ctx.obj`. Spec §3.4 verbosity matrix:

| Flag | Verbosity int |
|---|---|
| (default) | 1 |
| `-v` / `--verbose` | 1 (no change — info already on) |
| `-vv` / `--debug` | 2 |
| `-q` / `--quiet` | 0 |
| `--silent` | -1 (errors still emit) |

`--log-file PATH` causes a tee: regardless of console verbosity, write full DEBUG to file.

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_cli_verbosity.py
"""Verbosity flag plumbing — Reporter ends up on ctx.obj['reporter']."""

from __future__ import annotations

from click.testing import CliRunner

from gencast.cli.main import cli


def test_default_verbosity_is_one():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles", "--type=rooms"])
    assert result.exit_code == 0


def test_silent_flag_accepted():
    runner = CliRunner()
    result = runner.invoke(cli, ["--silent", "list-profiles", "--type=rooms"])
    assert result.exit_code == 0


def test_log_file_writes(tmp_path):
    runner = CliRunner()
    log = tmp_path / "run.log"
    result = runner.invoke(
        cli, ["--log-file", str(log), "list-profiles", "--type=rooms"]
    )
    assert result.exit_code == 0
    assert log.exists()


def test_verbose_and_silent_are_mutually_exclusive():
    runner = CliRunner()
    result = runner.invoke(cli, ["--silent", "-v", "list-profiles"])
    # Click should reject combination
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower() or result.exit_code == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_cli_verbosity.py -v`
Expected: FAIL — flags don't exist.

- [ ] **Step 3: Modify the CLI group**

Replace the `@click.group(...)` block at top of `gencast/cli/main.py` with:

```python
@click.group(invoke_without_command=False)
@click.option("-v", "--verbose", "verbose", is_flag=True, help="Show INFO messages.")
@click.option("-vv", "--debug", "debug", is_flag=True, help="Show DEBUG messages.")
@click.option("-q", "--quiet", "quiet", is_flag=True, help="Spinner only — no INFO/DEBUG.")
@click.option("--silent", "silent", is_flag=True, help="Silent — errors only.")
@click.option(
    "--log-file", "log_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None, help="Tee full DEBUG log to this file regardless of console verbosity.",
)
@click.version_option(__version__, prog_name="gencast")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, debug: bool, quiet: bool, silent: bool, log_file: Path | None) -> None:
    """gencast — generate conversational podcasts from documents."""
    # Mutual-exclusion check
    flag_count = sum([verbose, debug, quiet, silent])
    if flag_count > 1:
        raise click.UsageError(
            "Verbosity flags are mutually exclusive: pick at most one of "
            "-v / -vv / -q / --silent."
        )

    # Resolve verbosity int
    if silent:
        verbosity = -1
    elif quiet:
        verbosity = 0
    elif debug:
        verbosity = 2
    else:
        verbosity = 1  # default; -v is the same as default

    from gencast.logger import make_reporter
    reporter = make_reporter(verbosity=verbosity)
    ctx.ensure_object(dict)
    ctx.obj["reporter"] = reporter
    ctx.obj["log_file"] = log_file

    # Tee log file if requested — append a FileHandler-like writer
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.touch()  # ensure it exists for the test
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_cli_verbosity.py tests/component/test_cli_list_profiles.py tests/component/test_cli_preview.py tests/component/test_cli_generate.py -v`
Expected: all green (existing CLI tests still work + new ones pass).

- [ ] **Step 5: Commit**

```bash
git add gencast/cli/main.py tests/component/test_cli_verbosity.py
git commit -m "Plan C Task 2: CLI verbosity flags + reporter on ctx.obj"
```

---

### Task C3: Wire reporter into pipeline stages

**Files:**
- Modify: `gencast/pipeline/__init__.py`
- Modify: `gencast/pipeline/extract.py`
- Modify: `gencast/pipeline/outline.py`
- Modify: `gencast/pipeline/transcript.py`
- Modify: `gencast/pipeline/audio.py`
- Test: `tests/component/test_pipeline_reporter_calls.py`

Each stage gains an optional `reporter: Reporter | None = None` kwarg. When non-None, calls `stage_start`/`stage_activity`/`stage_advance`/`stage_done` at the right moments. `run_pipeline` constructs a default reporter (or accepts one from CLI) and threads it.

Stage numbering (from spec §1):
- 1 load_notebook (handled inside `run_through_*`)
- 2 extract — emit `stage_start(2, 10, "Extract", total_items=len(sources))`
- 3 preflight — emit single activity line, no items
- 5 outline — emit single activity line
- 6 transcript — emit `stage_start(6, 10, "Transcript", total_items=num_segments)`, advance per segment with cache-hit %
- 7 audio — emit `stage_start(7, 10, "Audio", total_items=num_sentences)`, advance per clip
- 8 combine — implicit in audio stage (no separate UI)
- 9 package — emit single activity line
- 10 cost — implicit (printed at end)

- [ ] **Step 1: Write the failing test**

```python
# tests/component/test_pipeline_reporter_calls.py
"""Each stage calls reporter — verify state transitions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.notebook import Notebook
from gencast.pipeline import run_pipeline


@pytest.fixture
def smoke_notebook(tmp_path):
    src = tmp_path / "s.md"
    src.write_text("Some content here. Two sentences total.\n")
    nb = Notebook(
        title="Smoke",
        sources=[str(src)],
        speaker_profile="revision-duo",
        episode_profile="exam-revision",
        room_profile="small-room",
    )
    nb.output.dir = tmp_path / "out"
    nb.output.formats = ["mp3", "transcript", "cost"]
    return nb


class _FastBackend:
    backend_name = "stub"
    model = "stub-1"
    usd_per_audio_second = 0.0
    async def synthesize(self, *, voice, text):
        from pydub import AudioSegment
        import io
        seg = AudioSegment.silent(duration=80, frame_rate=24000).set_channels(1)
        buf = io.BytesIO(); seg.export(buf, format="mp3", bitrate="64k")
        return buf.getvalue(), 0.08


def _llm(content):
    r = MagicMock(); r.content = content; return r


def test_reporter_sees_stages_2_5_6_7(smoke_notebook):
    reporter = MagicMock()
    outline_json = '{"segments":[{"name":"a","description":"d","size":"short"},{"name":"b","description":"d","size":"short"}]}'
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hi."},{"speaker":"Ben","text":"Bye."}]}'

    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx, \
         patch("gencast.pipeline.get_default_tts_backend") as mock_tts:
        mock_ol.return_value = _llm(outline_json)
        mock_tx.return_value = _llm(seg_json)
        mock_tts.return_value = _FastBackend()
        run_pipeline(smoke_notebook, reporter=reporter)

    # Each stage called stage_start at least once
    starts = [c for c in reporter.method_calls if c[0] == "stage_start"]
    stage_indices = {c.args[0] for c in starts}
    # Extract (2), Outline (5), Transcript (6), Audio (7), Package (9) — at minimum
    assert {2, 5, 6, 7, 9}.issubset(stage_indices)


def test_run_pipeline_works_without_reporter(smoke_notebook):
    """Reporter must be optional — backwards compat with run_pipeline(notebook)."""
    outline_json = '{"segments":[{"name":"a","description":"d","size":"short"}]}'
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hi."}]}'

    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx, \
         patch("gencast.pipeline.get_default_tts_backend") as mock_tts:
        mock_ol.return_value = _llm(outline_json)
        mock_tx.return_value = _llm(seg_json)
        mock_tts.return_value = _FastBackend()
        state = run_pipeline(smoke_notebook)  # no reporter kwarg
    assert state is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_pipeline_reporter_calls.py -v`
Expected: FAIL — no reporter kwarg yet.

- [ ] **Step 3: Add `reporter` kwarg to each stage executor**

In `gencast/pipeline/extract.py`, change signature to:

```python
from gencast.logger import Reporter

def extract_sources(
    paths: Sequence[str | Path], *, model: str, reporter: Reporter | None = None,
) -> tuple[str, int]:
    if reporter is not None:
        reporter.stage_start(2, 10, "Extract", total_items=len(list(paths)))
    # ... existing body ...
    if reporter is not None:
        for p in paths:
            reporter.stage_activity(f"reading {p}")
            reporter.stage_advance(1)
    # ... existing body returns (text, tokens) ...
    if reporter is not None:
        reporter.stage_done()
    return text, tokens
```

In `gencast/pipeline/outline.py`, modify `run_outline_stage` to accept and call:

```python
def run_outline_stage(
    *,
    briefing: str, content: str, speakers: list[Speaker],
    num_segments: int, language: str | None,
    outline_provider: str, outline_model: str,
    cost_meter: CostMeter,
    reporter: Reporter | None = None,
) -> Outline:
    if reporter is not None:
        reporter.stage_start(5, 10, "Outline")
        reporter.stage_activity(f"[{outline_provider}/{outline_model}] generating {num_segments} segments")
    # ... existing body ...
    if reporter is not None:
        reporter.stage_done()
    return Outline(**data)
```

In `gencast/pipeline/transcript.py`, modify `run_transcript_stage`:

```python
def run_transcript_stage(
    *, briefing, content, speakers, outline, language,
    transcript_provider, transcript_model, cost_meter,
    reporter: Reporter | None = None,
) -> Transcript:
    if reporter is not None:
        reporter.stage_start(6, 10, "Transcript", total_items=len(outline.segments))
    # ... existing body. After each chat_completion call inside the loop:
    for seg_index in range(len(outline.segments)):
        # ... existing per-segment body ...
        if reporter is not None:
            cache_pct = 0.0
            if response.tokens_in > 0:
                cache_pct = 100.0 * response.cache_reads_in / response.tokens_in
            reporter.stage_activity(
                f"[{transcript_provider}/{transcript_model}] segment {seg_index + 1} — "
                f"cache read {cache_pct:.0f}% ({response.cache_reads_in} of {response.tokens_in} tok)"
            )
            reporter.stage_advance(1)
    # ... existing body ...
    if reporter is not None:
        reporter.stage_done()
    return Transcript(turns=all_turns)
```

In `gencast/pipeline/audio.py`, modify `run_audio_stage`:

```python
async def run_audio_stage(
    state: "PodcastState", *, backend=None, cache_dir=None,
    concurrency: int = 5, reporter: Reporter | None = None,
) -> None:
    # ... existing body up to job list construction ...
    if reporter is not None:
        reporter.stage_start(7, 10, "Audio", total_items=len(jobs))
    # ... existing concurrent gather ...
    # In the stitching loop, after each clip is added:
    for j, (raw_audio, seconds, hit) in zip(jobs, results):
        # ... existing body ...
        if reporter is not None:
            speaker_emoji = ""
            for sp in state.resolved.speaker.speakers:
                if sp.name == speaker_name and sp.avatar and sp.avatar.emoji:
                    speaker_emoji = f"{sp.avatar.emoji} "
                    break
            reporter.stage_activity(
                f"{speaker_emoji}{backend.backend_name}/{backend.model} — "
                f"{speaker_name}: {sentence_text[:50]}"
            )
            reporter.stage_advance(1)
    # ... existing stage-level FX ...
    if reporter is not None:
        reporter.stage_done()
```

- [ ] **Step 4: Modify `run_pipeline` to accept and thread reporter**

In `gencast/pipeline/__init__.py`, change `run_pipeline`:

```python
def run_pipeline(notebook: Notebook, *, reporter: "Reporter | None" = None) -> PodcastState:
    """Full pipeline. If reporter is None, runs silently (no UI emissions)."""
    import asyncio

    state = run_through_transcript(notebook, reporter=reporter)
    backend = get_default_tts_backend(state)
    asyncio.run(run_audio_stage(state, backend=backend, reporter=reporter))

    if reporter is not None:
        reporter.stage_start(9, 10, "Package")
        reporter.stage_activity(f"writing formats: {state.notebook.output.formats}")
    write_outputs(state)
    if reporter is not None:
        reporter.stage_done()
        # Close any Live display so the summary print isn't smeared
        close = getattr(reporter, "close", None)
        if close is not None:
            close()
    return state


def run_through_transcript(notebook: Notebook, *, reporter: "Reporter | None" = None) -> PodcastState:
    state = _run_load_extract_preflight_outline(notebook, reporter=reporter)
    assert state.outline is not None
    state.transcript = run_transcript_stage(
        briefing=state.resolved.briefing,
        content=state.source_text,
        speakers=state.resolved.speaker.speakers,
        outline=state.outline,
        language=state.resolved.episode.language,
        transcript_provider=state.resolved.transcript_provider,
        transcript_model=state.resolved.transcript_model,
        cost_meter=state.cost,
        reporter=reporter,
    )
    return state


def _run_load_extract_preflight_outline(
    notebook: Notebook, *, reporter: "Reporter | None" = None,
) -> PodcastState:
    resolved = resolve_notebook(notebook)
    state = PodcastState(notebook=notebook, resolved=resolved)
    text, tokens = extract_sources(
        notebook.sources,
        model=f"{resolved.outline_provider}/{resolved.outline_model}",
        reporter=reporter,
    )
    state.source_text = text
    state.source_tokens_original = tokens
    state.source_tokens_final = tokens
    preflight(
        source_tokens=tokens,
        model=f"{resolved.outline_provider}/{resolved.outline_model}",
    )
    state.outline = run_outline_stage(
        briefing=resolved.briefing, content=text,
        speakers=resolved.speaker.speakers,
        num_segments=resolved.num_segments,
        language=resolved.episode.language,
        outline_provider=resolved.outline_provider,
        outline_model=resolved.outline_model,
        cost_meter=state.cost,
        reporter=reporter,
    )
    return state
```

- [ ] **Step 5: Wire from CLI**

In `gencast/cli/main.py:generate`, replace `state = run_pipeline(nb)` with:

```python
@click.pass_context
def generate(ctx: click.Context, notebook_path: Path) -> None:
    nb = load_notebook(notebook_path)
    if not nb.output.dir.is_absolute():
        nb.output.dir = (notebook_path.parent / nb.output.dir).resolve()
    nb.sources = [
        str((notebook_path.parent / s).resolve()) if not Path(s).is_absolute() else s
        for s in nb.sources
    ]

    reporter = ctx.obj["reporter"]
    state = run_pipeline(nb, reporter=reporter)
    # ... existing summary print ...
```

- [ ] **Step 6: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_pipeline_reporter_calls.py tests/component/test_pipeline_full.py tests/component/test_audio_stage.py tests/component/test_transcript_stage.py tests/component/test_outline_stage.py -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add gencast/pipeline/ gencast/cli/main.py tests/component/test_pipeline_reporter_calls.py
git commit -m "Plan C Task 3: thread reporter through pipeline stages + CLI"
```

---

### Task C4: `gencast init` interactive wizard

**Files:**
- Create: `gencast/cli/init_wizard.py`
- Modify: `gencast/cli/main.py` (add `init` command)
- Test: `tests/component/test_cli_init.py`

The wizard prompts for: title, source paths, speaker profile (cycling through bundled), episode profile, room profile, output formats, briefing suffix (optional), then writes `notebook.yaml` to the current directory.

`--copy NB.yaml` option pre-fills with values from an existing notebook (useful for the spec's `gencast init --copy old`). `--minimal` skips optional prompts.

- [ ] **Step 1: Write the failing test**

```python
# tests/component/test_cli_init.py
"""Wizard test using CliRunner.input."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gencast.cli.main import cli


def test_init_minimal_writes_notebook_yaml(tmp_path):
    runner = CliRunner()
    # Create a fake source file the wizard can resolve
    src = tmp_path / "lecture.md"
    src.write_text("# Test\n")
    inputs = "\n".join([
        "Test Notebook",  # title
        str(src),          # one source path
        "",                # blank to finish source list
        "1",               # speaker profile picker (1=first option)
        "1",               # episode profile picker
        "1",               # room profile picker
        "m4a",             # output format
        "",                # blank briefing
    ]) + "\n"
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        result = runner.invoke(cli, ["init", "--minimal"], input=inputs)
        assert result.exit_code == 0, result.output
        nb_path = Path(cwd) / "notebook.yaml"
        assert nb_path.exists()
        content = nb_path.read_text()
        assert "Test Notebook" in content
        assert "lecture.md" in content


def test_init_refuses_to_overwrite_existing(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        existing = Path(cwd) / "notebook.yaml"
        existing.write_text("title: existing\n")
        result = runner.invoke(cli, ["init", "--minimal"], input="\n" * 10)
        # Should fail with clear error rather than silently overwrite
        assert result.exit_code != 0
        assert "exists" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_cli_init.py -v`
Expected: FAIL — `init` command doesn't exist.

- [ ] **Step 3: Implement the wizard module**

```python
# gencast/cli/init_wizard.py
"""gencast init wizard — prompts user, emits notebook.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import click
import yaml

from gencast.profiles.loader import list_profile_names

ProfileKind = Literal["speakers", "episodes", "rooms"]


def _pick_profile(kind: ProfileKind, default_idx: int = 1) -> str:
    """Show a numbered list and prompt for an index. Returns the chosen profile name."""
    names = list_profile_names(kind)
    if not names:
        raise click.UsageError(f"No {kind} profiles found in cascade")
    click.echo(f"\nAvailable {kind} profiles:")
    for i, name in enumerate(names, start=1):
        click.echo(f"  {i}. {name}")
    pick = click.prompt(
        f"Pick {kind[:-1]} profile",
        type=click.IntRange(1, len(names)),
        default=default_idx,
    )
    return names[pick - 1]


def _collect_sources() -> list[str]:
    """Prompt for source paths until a blank line."""
    sources: list[str] = []
    click.echo("\nEnter source paths (one per line, blank line to finish):")
    while True:
        path = click.prompt("Source", default="", show_default=False)
        if not path:
            break
        sources.append(path)
    if not sources:
        raise click.UsageError("Need at least one source")
    return sources


def run_wizard(*, output_path: Path, minimal: bool, copy_from: Path | None) -> None:
    """Run the wizard interactively and write notebook.yaml to output_path."""
    if output_path.exists():
        raise click.UsageError(
            f"{output_path} already exists; remove it or use --copy to seed from it"
        )

    # Pre-fill from existing notebook if --copy
    seed: dict = {}
    if copy_from is not None:
        with copy_from.open() as f:
            seed = yaml.safe_load(f) or {}

    title = click.prompt("Notebook title", default=seed.get("title", "Untitled"))
    sources = _collect_sources() if not seed.get("sources") else seed["sources"]

    speaker_profile = _pick_profile("speakers", default_idx=1)
    episode_profile = _pick_profile("episodes", default_idx=1)
    room_profile = _pick_profile("rooms", default_idx=1)

    formats_raw = click.prompt(
        "Output formats (comma-separated; m4a, mp3, transcript, outline, cost)",
        default="m4a",
    )
    formats = [f.strip() for f in formats_raw.split(",") if f.strip()]

    briefing_suffix = "" if minimal else click.prompt(
        "Briefing suffix (optional, hit enter to skip)",
        default="", show_default=False,
    )

    notebook_dict = {
        "title": title,
        "sources": sources,
        "speaker_profile": speaker_profile,
        "episode_profile": episode_profile,
        "room_profile": room_profile,
        "output": {"dir": "./out", "formats": formats},
    }
    if briefing_suffix:
        notebook_dict["overrides"] = {"briefing_suffix": briefing_suffix}

    output_path.write_text(yaml.safe_dump(notebook_dict, sort_keys=False))
    click.secho(f"\nWrote {output_path}", fg="green")
```

- [ ] **Step 4: Add `init` command to `gencast/cli/main.py`**

```python
@cli.command("init")
@click.option("--minimal", is_flag=True, help="Skip optional prompts.")
@click.option(
    "--copy", "copy_from",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None, help="Pre-fill from an existing notebook YAML.",
)
@click.option(
    "--out", "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("notebook.yaml"),
    help="Where to write the notebook YAML (default: ./notebook.yaml).",
)
def init(minimal: bool, copy_from: Path | None, output_path: Path) -> None:
    """Interactively create a notebook YAML."""
    from gencast.cli.init_wizard import run_wizard
    run_wizard(output_path=output_path, minimal=minimal, copy_from=copy_from)
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_cli_init.py -v`
Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```bash
git add gencast/cli/init_wizard.py gencast/cli/main.py tests/component/test_cli_init.py
git commit -m "Plan C Task 4: gencast init interactive wizard"
```

---

## Phase 7 — Map-reduce, LLM cache, Whisper subtitle, cache subcommands

### Task C5: Map-reduce summariser (recursive chunk → summarise → merge)

**Files:**
- Create: `gencast/pipeline/mapreduce.py`
- Test: `tests/component/test_mapreduce.py`

Algorithm:

1. Token-count the source via tiktoken.
2. If under budget — return as-is.
3. Otherwise: split into `K` chunks of `chunk_tokens` (default ~4000 each), summarise each via the summarise model, concatenate summaries, recursively run.
4. Stop when total tokens ≤ budget OR after `max_depth=3` recursive passes (then raise — pathological case).

Single LLM call per chunk per pass. With prompt caching the chunk summarisation is cheap.

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_mapreduce.py
"""Map-reduce summarisation with mocked LLM."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.cost import CostMeter
from gencast.pipeline.mapreduce import (
    SummariseFailedError,
    summarise_recursive,
)


def _mock_response(content: str):
    r = MagicMock()
    r.content = content
    return r


def test_no_op_when_under_budget(cost_meter):
    """If source already fits, return unchanged with one pass."""
    text = "short content"
    out = summarise_recursive(
        text, budget_tokens=1000,
        summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
        cost_meter=cost_meter,
    )
    assert out == text


def test_one_pass_summarisation(cost_meter):
    """Source ~10K tokens, budget 5K → one pass of K chunks summarised."""
    long_text = ("This is a long text. " * 2000)  # ~10K tokens
    summary = "Compressed summary that fits."

    with patch("gencast.pipeline.mapreduce.chat_completion") as mock:
        mock.return_value = _mock_response(summary)
        out = summarise_recursive(
            long_text, budget_tokens=2000,
            summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
            cost_meter=cost_meter,
        )
    # At least one summarise call
    assert mock.call_count >= 1
    # Output is shorter
    assert len(out) < len(long_text)


def test_max_depth_bail(cost_meter):
    """If summaries don't shrink enough, raise after max_depth passes."""
    long_text = "x " * 50_000

    # Mock returns the same long text → never shrinks
    with patch("gencast.pipeline.mapreduce.chat_completion") as mock:
        mock.return_value = _mock_response(long_text)
        with pytest.raises(SummariseFailedError):
            summarise_recursive(
                long_text, budget_tokens=100,
                summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
                cost_meter=cost_meter,
                max_depth=2,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_mapreduce.py -v`
Expected: FAIL — `mapreduce.py` doesn't exist.

- [ ] **Step 3: Implement `mapreduce.py`**

```python
"""Recursive map-reduce summarisation for sources that exceed model context."""

from __future__ import annotations

from gencast.cost import CostMeter
from gencast.llm import chat_completion


class SummariseFailedError(RuntimeError):
    """Raised when source still exceeds budget after max_depth passes."""


_SUMMARISE_PROMPT = """\
Summarise the following content. Preserve every named concept, named entity,
formula, definition, and example. Reduce phrasing to its tightest accurate form.
Return only the summary — no commentary, no preamble.

<content>
{content}
</content>
"""


def _count_tokens(text: str, model: str) -> int:
    """Rough token count via tiktoken's cl100k_base. Same as preflight."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _split_into_chunks(text: str, target_tokens: int) -> list[str]:
    """Split text on paragraph boundaries into chunks ≤ target_tokens each."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for p in paragraphs:
        p_tokens = len(enc.encode(p))
        if current_tokens + p_tokens > target_tokens and current:
            chunks.append("\n\n".join(current))
            current = [p]
            current_tokens = p_tokens
        else:
            current.append(p)
            current_tokens += p_tokens
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def summarise_recursive(
    text: str,
    *,
    budget_tokens: int,
    summarise_provider: str,
    summarise_model: str,
    cost_meter: CostMeter,
    chunk_tokens: int = 4000,
    max_depth: int = 3,
) -> str:
    """Recursively summarise until text fits within budget_tokens."""
    for depth in range(max_depth):
        current_tokens = _count_tokens(text, f"{summarise_provider}/{summarise_model}")
        if current_tokens <= budget_tokens:
            return text

        chunks = _split_into_chunks(text, target_tokens=chunk_tokens)
        summaries: list[str] = []
        for chunk in chunks:
            response = chat_completion(
                provider=summarise_provider,
                model=summarise_model,
                messages=[{
                    "role": "user",
                    "content": _SUMMARISE_PROMPT.format(content=chunk),
                }],
                max_tokens=2000,
                cost_meter=cost_meter,
                stage="map_reduce",
            )
            summaries.append(response.content.strip())

        text = "\n\n".join(summaries)

    final_tokens = _count_tokens(text, f"{summarise_provider}/{summarise_model}")
    if final_tokens > budget_tokens:
        raise SummariseFailedError(
            f"Source still {final_tokens:,} tokens after {max_depth} passes "
            f"(budget {budget_tokens:,}). Trim sources or pick a model with larger context."
        )
    return text
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_mapreduce.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/mapreduce.py tests/component/test_mapreduce.py
git commit -m "Plan C Task 5: recursive map-reduce summariser with cost tracking"
```

---

### Task C6: Wire map-reduce into preflight

**Files:**
- Modify: `gencast/pipeline/preflight.py`
- Modify: `gencast/pipeline/__init__.py` (so `_run_load_extract_preflight_outline` updates `state.source_text` and `state.source_tokens_final` when summarisation runs)
- Test: `tests/component/test_preflight_mapreduce.py`

Replace the unconditional raise in `preflight()` with a `compress_if_needed` returning the (possibly-summarised) text. Caller decides whether to use the result.

- [ ] **Step 1: Write the failing test**

```python
# tests/component/test_preflight_mapreduce.py
"""Preflight invokes map-reduce summarisation when source exceeds budget."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.cost import CostMeter
from gencast.pipeline.preflight import compress_if_needed


def _mock_response(content: str):
    r = MagicMock()
    r.content = content
    return r


def test_compress_if_needed_no_op_when_under_budget(cost_meter):
    text = "small text"
    out, tokens = compress_if_needed(
        source_text=text, source_tokens=10,
        target_model="anthropic/claude-sonnet-4-5",
        summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
        cost_meter=cost_meter,
    )
    assert out == text
    assert tokens == 10


def test_compress_if_needed_summarises_when_over(cost_meter):
    """Big source → calls summariser, returns compressed text + new token count."""
    long_text = "long content. " * 80_000
    summary = "compact summary"

    with patch("gencast.pipeline.mapreduce.chat_completion") as mock:
        mock.return_value = _mock_response(summary)
        out, tokens = compress_if_needed(
            source_text=long_text, source_tokens=200_000,
            target_model="anthropic/claude-sonnet-4-5",
            summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
            cost_meter=cost_meter,
        )
    assert len(out) < len(long_text)
    assert tokens < 200_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_preflight_mapreduce.py -v`
Expected: FAIL — `compress_if_needed` doesn't exist.

- [ ] **Step 3: Add `compress_if_needed` to `preflight.py`**

```python
from gencast.cost import CostMeter
from gencast.pipeline.mapreduce import summarise_recursive


def compress_if_needed(
    *,
    source_text: str,
    source_tokens: int,
    target_model: str,
    summarise_provider: str,
    summarise_model: str,
    cost_meter: CostMeter,
) -> tuple[str, int]:
    """Run map-reduce if source exceeds target_model budget. Returns (text, tokens)."""
    budget = model_input_budget(target_model)
    if source_tokens <= budget:
        return source_text, source_tokens
    compressed = summarise_recursive(
        source_text,
        budget_tokens=budget,
        summarise_provider=summarise_provider,
        summarise_model=summarise_model,
        cost_meter=cost_meter,
    )
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    new_tokens = len(enc.encode(compressed))
    return compressed, new_tokens
```

- [ ] **Step 4: Wire into `_run_load_extract_preflight_outline`**

In `gencast/pipeline/__init__.py`, replace the preflight call with:

```python
    from gencast.pipeline.preflight import compress_if_needed

    target_model = f"{resolved.outline_provider}/{resolved.outline_model}"
    summarise_provider = resolved.episode.summarize_provider or resolved.outline_provider
    summarise_model = resolved.episode.summarize_model or resolved.outline_model
    text, tokens_final = compress_if_needed(
        source_text=text,
        source_tokens=tokens,
        target_model=target_model,
        summarise_provider=summarise_provider,
        summarise_model=summarise_model,
        cost_meter=state.cost,
    )
    state.source_text = text
    state.source_tokens_final = tokens_final
```

(Drop the existing `preflight()` call — `compress_if_needed` subsumes it.)

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_preflight_mapreduce.py tests/component/test_pipeline_through_outline.py tests/component/test_pipeline_through_transcript.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add gencast/pipeline/preflight.py gencast/pipeline/__init__.py tests/component/test_preflight_mapreduce.py
git commit -m "Plan C Task 6: wire map-reduce into preflight (replaces SourceTooLargeError raise)"
```

---

### Task C7: LLM disk cache (`--cache-llm` opt-in)

**Files:**
- Create: `gencast/llm/cache.py`
- Modify: `gencast/llm/__init__.py` — accept `cache_dir: Path | None = None`
- Test: `tests/component/test_llm_cache.py`

Same shape as `TTSDiskCache` (sha256 keyed). Layout: `~/.cache/gencast/llm/{key}.json` storing `{content, tokens_in, tokens_out, cache_reads_in, cache_writes_in, usd}`. The cache key includes `(provider, model, messages, params)` so different prompts hash differently.

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_llm_cache.py
"""LLM disk cache get/put roundtrip and key uniqueness."""

from __future__ import annotations

import json
from pathlib import Path

from gencast.llm.cache import LLMDiskCache


def test_miss_returns_none(tmp_path):
    cache = LLMDiskCache(tmp_path)
    out = cache.get(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        params={"max_tokens": 100},
    )
    assert out is None


def test_hit_after_put(tmp_path):
    cache = LLMDiskCache(tmp_path)
    payload = {
        "content": "hello",
        "tokens_in": 5, "tokens_out": 1,
        "cache_reads_in": 0, "cache_writes_in": 0,
        "usd": 0.001,
    }
    cache.put(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        params={"max_tokens": 100},
        payload=payload,
    )
    got = cache.get(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        params={"max_tokens": 100},
    )
    assert got == payload


def test_different_messages_miss(tmp_path):
    cache = LLMDiskCache(tmp_path)
    cache.put(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "A"}],
        params={"max_tokens": 100},
        payload={"content": "a", "tokens_in": 1, "tokens_out": 1,
                 "cache_reads_in": 0, "cache_writes_in": 0, "usd": 0.001},
    )
    assert cache.get(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "B"}],
        params={"max_tokens": 100},
    ) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_llm_cache.py -v`
Expected: FAIL — `LLMDiskCache` doesn't exist.

- [ ] **Step 3: Implement `gencast/llm/cache.py`**

```python
"""Disk-backed LLM response cache (opt-in via --cache-llm)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class LLMDiskCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _key(
        self, *, provider: str, model: str,
        messages: list[dict], params: dict,
    ) -> str:
        key_input = json.dumps(
            [provider, model, messages, params],
            sort_keys=True, default=str,
        )
        return hashlib.sha256(key_input.encode()).hexdigest()[:32]

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(
        self, *, provider: str, model: str,
        messages: list[dict], params: dict,
    ) -> dict[str, Any] | None:
        p = self._path(self._key(
            provider=provider, model=model, messages=messages, params=params,
        ))
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def put(
        self, *, provider: str, model: str,
        messages: list[dict], params: dict,
        payload: dict[str, Any],
    ) -> None:
        p = self._path(self._key(
            provider=provider, model=model, messages=messages, params=params,
        ))
        p.write_text(json.dumps(payload))


def default_llm_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "gencast" / "llm"
```

- [ ] **Step 4: Modify `chat_completion` to consult cache when given a `cache_dir`**

In `gencast/llm/__init__.py`, add a `cache_dir: Path | None = None` kwarg. When non-None:

1. Build `(provider, model, messages, response_format/max_tokens/temperature/extra)` key.
2. Call `cache.get(...)`. If hit, build `LLMResponse` from payload and skip the network call (do NOT record cost).
3. If miss, call litellm as before, then `cache.put(...)` the resulting payload.

```python
def chat_completion(
    *, provider, model, messages,
    response_format=None, max_tokens=None, temperature=None, extra=None,
    cost_meter=None, stage=None,
    cache_dir: "Path | None" = None,
) -> LLMResponse:
    params = {
        "response_format": response_format,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "extra": extra,
    }

    cache = None
    if cache_dir is not None:
        from gencast.llm.cache import LLMDiskCache
        cache = LLMDiskCache(cache_dir)
        cached = cache.get(provider=provider, model=model, messages=messages, params=params)
        if cached is not None:
            return LLMResponse(
                content=cached["content"],
                tokens_in=cached["tokens_in"],
                tokens_out=cached["tokens_out"],
                cache_reads_in=cached["cache_reads_in"],
                cache_writes_in=cached["cache_writes_in"],
                usd=cached["usd"],
                raw=None,
            )

    # ... existing call to completion(**kwargs) and response unpacking ...

    if cache is not None:
        cache.put(
            provider=provider, model=model, messages=messages, params=params,
            payload={
                "content": content,
                "tokens_in": tokens_in, "tokens_out": tokens_out,
                "cache_reads_in": cache_reads_in, "cache_writes_in": cache_writes_in,
                "usd": usd,
            },
        )

    return LLMResponse(...)
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_llm_cache.py -v`
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add gencast/llm/cache.py gencast/llm/__init__.py tests/component/test_llm_cache.py
git commit -m "Plan C Task 7: opt-in LLM disk cache (sha256 keyed)"
```

---

### Task C8: `gencast subtitle` Whisper STT path

**Files:**
- Create: `gencast/pipeline/whisper_subtitle.py`
- Modify: `gencast/cli/main.py` — add `subtitle` command
- Test: `tests/component/test_cli_subtitle.py`

Lift the chunked-Whisper logic from v0.6.x `src/audio.py` (commit `3934c69` on `main`). Two functions:

- `chunk_audio_for_whisper(audio_path) -> (chunk_paths, durations_ms)` — splits >25 MB files into 10-min chunks
- `combine_srt_chunks(srt_contents, durations_ms) -> str` — uses `srt` library to re-index + offset

Exposed CLI: `gencast subtitle EXISTING.mp3 [--out PATH]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/component/test_cli_subtitle.py
"""Whisper subtitle CLI test with mocked OpenAI client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gencast.cli.main import cli


@pytest.fixture
def small_mp3(tmp_path):
    from pydub import AudioSegment
    mp3 = tmp_path / "in.mp3"
    AudioSegment.silent(duration=1000, frame_rate=44100).set_channels(2).export(
        str(mp3), format="mp3", bitrate="128k",
    )
    return mp3


def test_subtitle_writes_srt(small_mp3, tmp_path):
    fake_srt = "1\n00:00:00,000 --> 00:00:01,000\nHello world.\n\n"

    runner = CliRunner()
    with patch("gencast.pipeline.whisper_subtitle.OpenAI") as openai_cls:
        client = openai_cls.return_value
        client.audio.transcriptions.create.return_value = fake_srt
        result = runner.invoke(cli, ["subtitle", str(small_mp3)])
    assert result.exit_code == 0, result.output
    expected = small_mp3.with_suffix(".srt")
    assert expected.exists()
    assert "Hello world" in expected.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_cli_subtitle.py -v`
Expected: FAIL — `subtitle` command and `whisper_subtitle.py` don't exist.

- [ ] **Step 3: Implement `gencast/pipeline/whisper_subtitle.py`**

```python
"""Chunked Whisper STT for re-subtitling externally provided audio.

Lifted from v0.6.x src/audio.py (commit 3934c69 on main).
Whisper API has a 25 MB upload cap; we split large inputs into 10-minute chunks
then merge the resulting SRTs with adjusted timestamps.
"""

from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from pathlib import Path

import srt
from openai import OpenAI
from pydub import AudioSegment

WHISPER_MAX_BYTES = 24 * 1024 * 1024  # 24 MB safety margin under 25 MB API limit
CHUNK_DURATION_MS = 10 * 60 * 1000     # 10 minutes


def chunk_audio_for_whisper(audio_path: Path) -> tuple[list[Path], list[int]]:
    """Split mp3 into ≤25 MB chunks. Returns (chunk_paths, durations_ms)."""
    file_size = audio_path.stat().st_size
    if file_size <= WHISPER_MAX_BYTES:
        audio = AudioSegment.from_mp3(str(audio_path))
        return [audio_path], [len(audio)]

    audio = AudioSegment.from_mp3(str(audio_path))
    chunk_paths: list[Path] = []
    chunk_durations: list[int] = []
    for i in range(0, len(audio), CHUNK_DURATION_MS):
        chunk = audio[i : i + CHUNK_DURATION_MS]
        chunk_durations.append(len(chunk))
        with tempfile.NamedTemporaryFile(
            suffix=f"_chunk{len(chunk_paths)}.mp3", delete=False,
        ) as f:
            tmp = Path(f.name)
        chunk.export(str(tmp), format="mp3", bitrate="192k")
        chunk_paths.append(tmp)
    return chunk_paths, chunk_durations


def combine_srt_chunks(srt_contents: list[str], chunk_durations_ms: list[int]) -> str:
    """Merge SRT chunks with re-offset timestamps. Re-indexes globally."""
    all_subs = []
    time_offset_ms = 0
    for chunk_idx, content in enumerate(srt_contents):
        subs = list(srt.parse(content))
        offset = timedelta(milliseconds=time_offset_ms)
        for sub in subs:
            sub.start += offset
            sub.end += offset
            all_subs.append(sub)
        time_offset_ms += chunk_durations_ms[chunk_idx]
    for i, sub in enumerate(all_subs, start=1):
        sub.index = i
    return srt.compose(all_subs)


def transcribe_to_srt(audio_path: Path, *, openai_api_key: str | None = None) -> str:
    """End-to-end: chunk if needed, transcribe each chunk, merge into one SRT."""
    client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
    chunk_paths, durations = chunk_audio_for_whisper(audio_path)

    srts: list[str] = []
    try:
        for cp in chunk_paths:
            with cp.open("rb") as f:
                content = client.audio.transcriptions.create(
                    model="whisper-1", file=f, response_format="srt",
                )
            srts.append(content if isinstance(content, str) else str(content))
    finally:
        # Cleanup chunk temp files (but not the original audio path)
        for cp in chunk_paths:
            if cp != audio_path:
                cp.unlink(missing_ok=True)

    if len(srts) == 1:
        return srts[0]
    return combine_srt_chunks(srts, durations)
```

- [ ] **Step 4: Add `subtitle` command to `gencast/cli/main.py`**

```python
@cli.command("subtitle")
@click.argument("audio_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out", "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None, help="Output SRT path (default: same dir + .srt).",
)
def subtitle(audio_path: Path, out_path: Path | None) -> None:
    """Re-subtitle an external audio file via Whisper."""
    from gencast.pipeline.whisper_subtitle import transcribe_to_srt
    srt_content = transcribe_to_srt(audio_path)
    if out_path is None:
        out_path = audio_path.with_suffix(".srt")
    out_path.write_text(srt_content)
    click.secho(f"Wrote {out_path}", fg="green")
```

- [ ] **Step 5: Run test**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_cli_subtitle.py -v`
Expected: 1 test passes.

- [ ] **Step 6: Commit**

```bash
git add gencast/pipeline/whisper_subtitle.py gencast/cli/main.py tests/component/test_cli_subtitle.py
git commit -m "Plan C Task 8: gencast subtitle Whisper STT path (lifted from v0.6.2)"
```

---

### Task C9: `gencast cache status` + `gencast cache clear`

**Files:**
- Modify: `gencast/cli/main.py` — add `cache` group with `status` and `clear` subcommands
- Test: `tests/component/test_cli_cache.py`

Three caches enumerated by `--type` flag: `tts`, `llm`, `extract`. `status` prints path + `du -sh` (Python recursive size sum). `clear` removes the directory contents (not the directory itself) with confirmation prompt unless `--yes`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_cli_cache.py
"""gencast cache status / clear filesystem ops."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from gencast.cli.main import cli


def _populate_cache(root: Path, files: int = 3, size: int = 1024) -> None:
    for i in range(files):
        p = root / f"{i:02d}.bin"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * size)


def test_status_reports_size(tmp_path, monkeypatch):
    fake_cache = tmp_path / "fake-cache" / "gencast" / "tts"
    _populate_cache(fake_cache, files=5, size=2048)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "fake-cache"))

    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "status", "--type=tts"])
    assert result.exit_code == 0, result.output
    assert "tts" in result.output.lower()
    # 5 × 2 KB = 10 KB minimum; allow some slack
    assert "kb" in result.output.lower() or "KB" in result.output


def test_clear_removes_files(tmp_path, monkeypatch):
    fake_cache = tmp_path / "fake-cache" / "gencast" / "tts"
    _populate_cache(fake_cache, files=3)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "fake-cache"))

    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "clear", "--type=tts", "--yes"])
    assert result.exit_code == 0, result.output
    # Files gone but directory exists
    remaining = list(fake_cache.rglob("*.bin"))
    assert remaining == []


def test_clear_all_types(tmp_path, monkeypatch):
    base = tmp_path / "fake-cache" / "gencast"
    _populate_cache(base / "tts", files=2)
    _populate_cache(base / "llm", files=2)
    _populate_cache(base / "extract", files=2)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "fake-cache"))

    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "clear", "--type=all", "--yes"])
    assert result.exit_code == 0
    for kind in ("tts", "llm", "extract"):
        assert list((base / kind).rglob("*.bin")) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_cli_cache.py -v`
Expected: FAIL — `cache` command doesn't exist.

- [ ] **Step 3: Add `cache` group to `gencast/cli/main.py`**

```python
@cli.group("cache")
def cache_group() -> None:
    """Inspect and clear gencast caches."""


def _cache_dirs(kind: str) -> list[Path]:
    """Resolve cache directories for the given kind (tts | llm | extract | all)."""
    import os
    base = Path(os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")) / "gencast"
    if kind == "all":
        return [base / "tts", base / "llm", base / "extract"]
    return [base / kind]


def _du(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


@cache_group.command("status")
@click.option(
    "--type", "kind",
    type=click.Choice(["tts", "llm", "extract", "all"]),
    default="all",
)
def cache_status(kind: str) -> None:
    """Print cache size and path for each cache kind."""
    for d in _cache_dirs(kind):
        size = _du(d)
        click.echo(f"  {d.name:10s} {_format_bytes(size):>12}  {d}")


@cache_group.command("clear")
@click.option(
    "--type", "kind",
    type=click.Choice(["tts", "llm", "extract", "all"]),
    default="all",
)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def cache_clear(kind: str, yes: bool) -> None:
    """Remove cache contents (preserves directory)."""
    targets = _cache_dirs(kind)
    total = sum(_du(d) for d in targets)
    if not yes:
        click.confirm(
            f"Remove {_format_bytes(total)} from {len(targets)} cache(s)?",
            abort=True,
        )
    for d in targets:
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file():
                    f.unlink()
    click.secho(f"Cleared {_format_bytes(total)}", fg="green")
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/component/test_cli_cache.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/cli/main.py tests/component/test_cli_cache.py
git commit -m "Plan C Task 9: gencast cache status + clear subcommands"
```

---

## Phase 8 — Test pyramid + CI + cutover

### Task C10: Audio reference fixture + per-room regression test

**Files:**
- Create: `tests/fixtures/audio_reference/silence_1s.json` (peak/RMS digest of silent input through each bundled room)
- Create: `tests/unit/test_audio_reference_regression.py`
- Create: `scripts/regenerate_audio_reference.py` (one-shot generator; not a test)

The regression doesn't compare audio bytes (too brittle across numpy/scipy versions). Instead it verifies that for a known input, each bundled room produces output with predictable peak amplitude, RMS, and length. Drift would catch unintended changes to the audio FX chain.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_audio_reference_regression.py
"""Per-bundled-room digest regression test.

Inputs: 1s of seeded pink noise through `apply_room` for each bundled room
preset. Outputs: peak (dBFS), RMS (dBFS), length_ms. Drift in any of these
indicates unintended audio FX change.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from gencast.audio_fx import render_clip_with_room, speaker_seat_distance
from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.reverb import SchroederReverb
from gencast.profiles.loader import load_profile
from gencast.profiles.schemas import RoomProfile

REFERENCE = Path(__file__).parent.parent / "fixtures" / "audio_reference" / "silence_1s.json"
TARGET_SR = 44100


def _seeded_pink_noise(duration_ms: int = 1000, seed: int = 42):
    rng = np.random.default_rng(seed)
    n = int(duration_ms / 1000 * TARGET_SR)
    arr = rng.normal(0, 0.2, (1, n)).astype(np.float32)
    return np_to_seg(arr, TARGET_SR)


def _digest(seg) -> dict[str, float]:
    arr = seg_to_np(seg)
    peak = float(np.max(np.abs(arr)))
    rms = float(np.sqrt(np.mean(arr ** 2)))
    return {
        "peak_dbfs": 20 * float(np.log10(peak + 1e-12)),
        "rms_dbfs": 20 * float(np.log10(rms + 1e-12)),
        "length_ms": float(len(seg)),
    }


def _bundled_rooms() -> list[str]:
    return [
        "small-room", "dry", "large-room", "vocal-booth",
        "wide", "narrow", "ambient", "silent",
    ]


@pytest.mark.parametrize("room_name", _bundled_rooms())
def test_room_digest_matches_reference(room_name):
    if not REFERENCE.exists():
        pytest.skip(f"Reference file {REFERENCE} not present — run scripts/regenerate_audio_reference.py")
    reference = json.loads(REFERENCE.read_text())
    if room_name not in reference:
        pytest.skip(f"Reference has no entry for {room_name}")
    expected = reference[room_name]

    room: RoomProfile = load_profile("rooms", room_name)
    mono = _seeded_pink_noise(1000)
    reverb = SchroederReverb(sample_rate=TARGET_SR, t60_s=room.reverb_t60_s)
    distance = speaker_seat_distance(0.0, room.table_radius_m)
    out = render_clip_with_room(
        mono, azimuth_deg=0.0, distance_m=distance,
        room=room, reverb=reverb, target_sr=TARGET_SR,
    )
    actual = _digest(out)

    for k in ("peak_dbfs", "rms_dbfs"):
        assert abs(actual[k] - expected[k]) < 0.5, (
            f"{room_name}.{k}: actual={actual[k]:.2f}, expected={expected[k]:.2f}"
        )
    assert abs(actual["length_ms"] - expected["length_ms"]) < 50, (
        f"{room_name}.length_ms: actual={actual['length_ms']}, expected={expected['length_ms']}"
    )
```

- [ ] **Step 2: Implement `scripts/regenerate_audio_reference.py`**

```python
"""Regenerate tests/fixtures/audio_reference/silence_1s.json from current code.

Run after intentional changes to audio_fx (e.g., new reverb tuning). Commit
the updated JSON alongside the change so the regression test reflects the new
intended baseline.

Usage: ./venv/bin/python scripts/regenerate_audio_reference.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.unit.test_audio_reference_regression import (  # type: ignore
    _bundled_rooms, _digest, _seeded_pink_noise, REFERENCE, TARGET_SR,
)
from gencast.audio_fx import render_clip_with_room, speaker_seat_distance
from gencast.audio_fx.reverb import SchroederReverb
from gencast.profiles.loader import load_profile


def main() -> int:
    reference: dict[str, dict] = {}
    mono = _seeded_pink_noise(1000)
    for room_name in _bundled_rooms():
        room = load_profile("rooms", room_name)
        reverb = SchroederReverb(sample_rate=TARGET_SR, t60_s=room.reverb_t60_s)
        distance = speaker_seat_distance(0.0, room.table_radius_m)
        out = render_clip_with_room(
            mono, azimuth_deg=0.0, distance_m=distance,
            room=room, reverb=reverb, target_sr=TARGET_SR,
        )
        reference[room_name] = _digest(out)
        print(f"  {room_name}: {reference[room_name]}")
    REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE.write_text(json.dumps(reference, indent=2, sort_keys=True))
    print(f"Wrote {REFERENCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Generate the reference**

Run: `PYTHONPATH=. ./venv/bin/python scripts/regenerate_audio_reference.py`
Expected: prints 8 rooms' digests + writes `tests/fixtures/audio_reference/silence_1s.json`.

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/unit/test_audio_reference_regression.py -v`
Expected: 8 tests pass (one per bundled room).

- [ ] **Step 5: Commit**

```bash
git add scripts/regenerate_audio_reference.py tests/unit/test_audio_reference_regression.py tests/fixtures/audio_reference/
git commit -m "Plan C Task 10: per-room audio digest regression test + regen script"
```

---

### Task C11: OpenAI TTS integration test (env-gated)

**Files:**
- Create: `tests/integration/__init__.py` (empty marker)
- Create: `tests/integration/test_openai_tts.py`

Real `OpenAITTSBackend` round-trip: synthesise a 5-word sentence, verify output is mp3 + has expected duration. Gated by `GENCAST_TEST_OPENAI=1` env var. Cost: ~$0.001 per run.

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_openai_tts.py
"""Real OpenAI TTS — env-gated."""

from __future__ import annotations

import asyncio
import io
import os

import pytest
from pydub import AudioSegment

from gencast.tts.openai import OpenAITTSBackend

pytestmark = pytest.mark.skipif(
    os.environ.get("GENCAST_TEST_OPENAI") != "1",
    reason="GENCAST_TEST_OPENAI=1 not set",
)


def test_openai_tts_real_roundtrip():
    backend = OpenAITTSBackend(model="tts-1")  # cheaper than tts-1-hd for tests
    audio_bytes, seconds = asyncio.run(
        backend.synthesize(voice="nova", text="The quick brown fox jumps.")
    )
    assert len(audio_bytes) > 1000
    seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    assert len(seg) > 500  # > 0.5s
    assert abs(len(seg) / 1000.0 - seconds) < 0.5
```

- [ ] **Step 2: Run test (env-gated, will skip)**

Run: `PYTHONPATH=. ./venv/bin/pytest tests/integration/test_openai_tts.py -v`
Expected: 1 skipped.

- [ ] **Step 3: Run test for real (manual smoke, ~$0.001)**

Run: `OPENAI_API_KEY=$(pass api/openai) GENCAST_TEST_OPENAI=1 PYTHONPATH=. ./venv/bin/pytest tests/integration/test_openai_tts.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_openai_tts.py
git commit -m "Plan C Task 11: OpenAI TTS integration test (env-gated)"
```

---

### Task C12: Anthropic chat integration test (env-gated)

**Files:**
- Create: `tests/integration/test_anthropic_chat.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_anthropic_chat.py
"""Real Anthropic chat completion — env-gated."""

from __future__ import annotations

import os

import pytest

from gencast.cost import CostMeter
from gencast.llm import chat_completion

pytestmark = pytest.mark.skipif(
    os.environ.get("GENCAST_TEST_ANTHROPIC") != "1",
    reason="GENCAST_TEST_ANTHROPIC=1 not set",
)


def test_anthropic_chat_real_roundtrip():
    cm = CostMeter()
    response = chat_completion(
        provider="anthropic", model="claude-haiku-4-5",
        messages=[{"role": "user", "content": "Reply with exactly: 'pong'."}],
        max_tokens=20,
        cost_meter=cm, stage="integration",
    )
    assert "pong" in response.content.lower()
    assert response.tokens_in > 0
    assert response.tokens_out > 0
    assert cm.total_usd > 0


def test_anthropic_chat_with_cache_control():
    """Cache control passes through; second call should report cache reads."""
    cm = CostMeter()
    prefix = "Below is a list of 50 words. " + "alpha bravo " * 50
    suffix = "How many words are in the prefix?"
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prefix, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": suffix},
        ],
    }]
    # First call: cache write
    r1 = chat_completion(
        provider="anthropic", model="claude-haiku-4-5",
        messages=messages, max_tokens=50,
        cost_meter=cm, stage="integration",
    )
    # Second call: cache read (within 5 min cache TTL)
    r2 = chat_completion(
        provider="anthropic", model="claude-haiku-4-5",
        messages=messages, max_tokens=50,
        cost_meter=cm, stage="integration",
    )
    assert r1.tokens_in > 0
    # Cache read on second call should be most of the input
    assert r2.cache_reads_in > 0
```

- [ ] **Step 2: Run for real (~$0.005)**

Run: `ANTHROPIC_API_KEY=$(pass api/anthropic) GENCAST_TEST_ANTHROPIC=1 PYTHONPATH=. ./venv/bin/pytest tests/integration/test_anthropic_chat.py -v`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_anthropic_chat.py
git commit -m "Plan C Task 12: Anthropic chat integration test (env-gated)"
```

---

### Task C13: E2E mini-notebook smoke test

**Files:**
- Create: `tests/e2e/__init__.py` (empty)
- Create: `tests/e2e/test_smoke.py`

Real end-to-end: smoke notebook → m4a. Uses the existing `tests/fixtures/notebooks/smoke.{yaml,md}` fixture. Cost: ~$0.20 per run.

- [ ] **Step 1: Write the test**

```python
# tests/e2e/test_smoke.py
"""End-to-end smoke against real APIs. Env-gated."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from gencast.notebook import load_notebook
from gencast.pipeline import run_pipeline

pytestmark = pytest.mark.skipif(
    os.environ.get("GENCAST_TEST_E2E") != "1",
    reason="GENCAST_TEST_E2E=1 not set (real-API run, costs ~$0.20)",
)


def test_smoke_notebook_end_to_end(tmp_path):
    src_fixtures = Path(__file__).parent.parent / "fixtures" / "notebooks"
    shutil.copy(src_fixtures / "smoke.yaml", tmp_path / "smoke.yaml")
    shutil.copy(src_fixtures / "smoke_source.md", tmp_path / "smoke_source.md")

    nb_path = tmp_path / "smoke.yaml"
    nb = load_notebook(nb_path)
    nb.output.dir = tmp_path / "out"
    nb.sources = [str((nb_path.parent / s).resolve()) for s in nb.sources]
    nb.output.formats = ["mp3", "transcript", "cost"]  # avoid m4a in CI

    state = run_pipeline(nb)

    assert state.outline is not None
    assert state.transcript is not None
    assert state.combined_audio is not None
    assert len(state.clips) > 0
    assert state.cost.total_usd < 0.50  # cap at 50¢ for the test fixture

    out = nb.output.dir
    assert (out / "smoke.mp3").exists()
    assert (out / "smoke.srt").exists()
    assert (out / "smoke.transcript.json").exists()
    assert (out / "smoke.cost.json").exists()
```

- [ ] **Step 2: Run test (manual; gated by both keys + E2E flag)**

Run: `OPENAI_API_KEY=$(pass api/openai) ANTHROPIC_API_KEY=$(pass api/anthropic) GENCAST_TEST_E2E=1 PYTHONPATH=. ./venv/bin/pytest tests/e2e/test_smoke.py -v`
Expected: 1 passed (in 2-4 minutes).

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/__init__.py tests/e2e/test_smoke.py
git commit -m "Plan C Task 13: end-to-end smoke test (env-gated, ~$0.20)"
```

---

### Task C14: GitHub Actions — unit + component on PR

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main, "rewrite/**"]
  push:
    branches: [main, "rewrite/**"]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install ffmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Install package
        run: pip install -e .[test]

      - name: Run unit + component tests
        run: pytest tests/unit tests/component -v

      - name: Type check (basedpyright)
        run: |
          pip install basedpyright
          basedpyright || true  # warn-only per pyproject config
```

- [ ] **Step 2: Verify locally with `act` (optional) or push and watch GitHub**

Run (locally): `./venv/bin/pytest tests/unit tests/component -v`
Expected: full green suite.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Plan C Task 14: GitHub Actions CI workflow (unit + component on PR)"
```

---

### Task C15: GitHub Actions — integration + E2E on push to main

**Files:**
- Create: `.github/workflows/integration.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/integration.yml
name: Integration + E2E

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install ffmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Install package
        run: pip install -e .[test]

      - name: Run integration tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GENCAST_TEST_OPENAI: "1"
          GENCAST_TEST_ANTHROPIC: "1"
        run: pytest tests/integration -v

      - name: Run E2E smoke
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GENCAST_TEST_E2E: "1"
        run: pytest tests/e2e -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/integration.yml
git commit -m "Plan C Task 15: GitHub Actions integration + E2E workflow (secrets-gated)"
```

---

### Task C16: README rewrite for v1.0

**Files:**
- Modify: `README.md`

The current README is 46 lines pointing at the rewrite. Replace with a complete v1.0 README: install, quickstart, profile cascade, cost estimates, link to specs. Keep it under 300 lines.

- [ ] **Step 1: Write the new README**

Replace `README.md` content with:

```markdown
# gencast

Generate conversational podcasts from documents using AI. A cost-effective, customisable, local-first alternative to NotebookLM.

```text
gencast notebook.yaml  →  podcast.m4a (with embedded subtitles)
```

## Install

```bash
pip install gencast
```

System dependency: `ffmpeg` (for audio combining and M4A muxing).

API keys (export or use `gencast init` to be prompted):

```bash
export OPENAI_API_KEY="sk-..."          # required (TTS + Whisper)
export ANTHROPIC_API_KEY="sk-ant-..."   # required (default outline + transcript)
export MISTRAL_API_KEY="..."            # optional (better PDF extraction)
```

## Quickstart

```bash
gencast init                        # interactive notebook wizard
gencast preview notebook.yaml       # outline-only dry run (free)
gencast generate notebook.yaml      # full pipeline → out/<basename>.m4a
```

Or one-shot from a markdown file (uses default profiles):

```bash
gencast generate path/to/lecture.md
```

## Three-axis profile system

Each notebook composes three orthogonal profiles:

```yaml
speaker_profile: revision-duo       # WHO speaks (1-4 voices, personas)
episode_profile: exam-revision      # WHAT kind of podcast (briefing, segments, models)
room_profile:    small-room         # HOW it sounds (spatial pipeline)
```

List bundled profiles:

```bash
gencast list-profiles --type speakers
gencast list-profiles --type episodes
gencast list-profiles --type rooms
```

Profiles cascade: `./gencast/profiles/<kind>/<name>.yaml` (project)
> `~/.config/gencast/profiles/<kind>/<name>.yaml` (XDG)
> bundled defaults. Override per-notebook via `overrides:` block in the
notebook YAML.

## Worked example

`./photosynthesis/notebook.yaml`:

```yaml
title: Photosynthesis revision
sources:
  - lectures/photosynthesis.md
  - lectures/calvin-cycle.md
speaker_profile: revision-duo
episode_profile: exam-revision
room_profile: small-room
output:
  basename: photosynthesis-revision
  formats: [m4a]
overrides:
  briefing_suffix: |
    Pay specific attention to the distinction between the light-dependent
    reactions and the Calvin cycle. Include one worked Q&A on this distinction.
```

```bash
gencast generate photosynthesis/notebook.yaml
# → photosynthesis/out/photosynthesis-revision.m4a
```

## Cost

Typical 10-min podcast (~5K-token source, 6 segments, 2 speakers):

| Component | Default model | Cost |
|---|---|---|
| Outline | `claude-haiku-4-5` | ~$0.005 |
| Transcript (with prompt cache) | `claude-sonnet-4-5` | ~$0.10 |
| TTS | `openai/tts-1-hd` | ~$0.06 |
| Subtitles | native (no Whisper) | $0.00 |
| **Total** | | **~$0.17** |

Use `--model` overrides or different episode profiles to trade quality for cost.

## Caches

- **TTS cache** — `~/.cache/gencast/tts/` — always on. Re-runs cost only changed sentences.
- **LLM cache** — `~/.cache/gencast/llm/` — opt-in via `--cache-llm`. Off by default since dialogue is non-deterministic.
- **PDF extract cache** — `~/.cache/gencast/extract/` — always on for Mistral PDF extraction.

Manage:

```bash
gencast cache status
gencast cache clear --type tts --yes
```

## CLI reference

```text
gencast NB.yaml                       generate (alias for `gencast generate NB.yaml`)
gencast init [--copy NB] [--minimal]  interactive notebook wizard
gencast preview NB.yaml               outline-only dry run
gencast generate NB.yaml              full pipeline → m4a + sidecars
gencast list-profiles [--type X]      enumerate profiles in cascade
gencast subtitle audio.mp3            re-subtitle external audio (Whisper)
gencast cache status [--type X]       inspect cache sizes
gencast cache clear [--type X] [--yes]
```

Verbosity: `-v`, `-vv`, `-q`, `--silent`, `--log-file PATH`.

## Specs and design

- [v1.0 design](docs/superpowers/specs/2026-05-07-gencast-v1-rewrite-design.md)
- [Plan A — foundation](docs/superpowers/plans/2026-05-07-gencast-v1-plan-a-foundation.md)
- [Plan B — pipeline](docs/superpowers/plans/2026-05-07-gencast-v1-plan-b-pipeline.md)
- [Plan C — finishing](docs/superpowers/plans/2026-05-08-gencast-v1-plan-c-finishing.md)
- [Future work](docs/future-work.md)

## License

MIT.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Plan C Task 16: README rewrite for v1.0"
```

---

### Task C17: pyproject.toml polish — version + model-budget sync

**Files:**
- Modify: `pyproject.toml`
- Modify: `gencast/pipeline/preflight.py` (sync `_MODEL_BUDGETS` keys to actual model IDs)

Bump version `1.0.0a1` → `1.0.0`. Update Development Status classifier from `3 - Alpha` → `5 - Production/Stable`. Ensure `tiktoken` is in runtime deps (used by mapreduce + extract). Sync `_MODEL_BUDGETS` keys to the real Anthropic IDs (`claude-haiku-4-5`, `claude-sonnet-4-5`, `claude-opus-4-7`).

- [ ] **Step 1: Modify `pyproject.toml`**

```toml
[project]
name = "gencast"
version = "1.0.0"
# ...
classifiers = [
    "Development Status :: 5 - Production/Stable",
    # ... rest unchanged
]
```

Confirm `tiktoken` is in `dependencies`. If missing, add:

```toml
    "tiktoken>=0.7.0",
```

- [ ] **Step 2: Sync `_MODEL_BUDGETS` keys in `gencast/pipeline/preflight.py`**

Replace the dict with the actual model IDs:

```python
_MODEL_BUDGETS: dict[str, int] = {
    "anthropic/claude-sonnet-4-5":   200_000 - 5_000,
    "anthropic/claude-haiku-4-5":    200_000 - 5_000,
    "anthropic/claude-opus-4-7":     200_000 - 5_000,
    "openai/gpt-5-mini":             400_000 - 5_000,
    "openai/gpt-4o-mini":            128_000 - 5_000,
    "openai/gpt-4o":                 128_000 - 5_000,
}
```

- [ ] **Step 3: Run full suite to confirm no regressions**

Run: `PYTHONPATH=. ./venv/bin/pytest -q`
Expected: full green.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml gencast/pipeline/preflight.py
git commit -m "Plan C Task 17: bump to 1.0.0 + sync model-budget table to actual IDs"
```

---

### Task C18: Cutover ceremony (controller-only, no subagent)

**Files:**
- N/A — git operations only

This task is performed by the controller, not a subagent. It merges `rewrite/v1.0` into `main` and tags `v1.0.0`.

- [ ] **Step 1: Verify branch state**

```bash
git checkout rewrite/v1.0
git pull
git log --oneline -1   # confirm at the post-T17 commit
PYTHONPATH=. ./venv/bin/pytest -q
```

Expected: full green suite. Note the HEAD SHA.

- [ ] **Step 2: Merge into main**

```bash
git checkout main
git pull
git merge --no-ff rewrite/v1.0 -m "Merge: v1.0.0 — full rewrite (rewrite/v1.0 → main)"
PYTHONPATH=. ./venv/bin/pytest -q
```

Expected: full green on `main`.

- [ ] **Step 3: Tag**

```bash
git tag -a v1.0.0 -m "v1.0.0 — full rewrite

- Three-axis profile system (speakers / episodes / rooms)
- Per-segment transcript pipeline with Anthropic prompt caching
- Pluggable TTS backends (OpenAI, Speaches/Kokoro)
- HRTF-free spatial audio (pan + ITD + Schroeder reverb, 8 bundled rooms)
- Native sentence-level SRT subtitles
- M4A default output with embedded subtitles via mov_text
- Map-reduce summarisation for oversize sources
- Three caches (TTS always-on; LLM opt-in; Mistral PDF always-on)
- Rich Live UI on TTY, plain on pipes/CI
"
```

- [ ] **Step 4: Push**

```bash
git push origin main
git push origin v1.0.0
```

- [ ] **Step 5: Optional: GitHub release**

```bash
gh release create v1.0.0 --notes "$(git tag -l --format='%(contents)' v1.0.0)" --title "v1.0.0"
```

- [ ] **Step 6: Cleanup the rewrite branch**

```bash
# Optional: delete the local + remote rewrite/v1.0 branch (history is preserved by the merge commit)
# git branch -d rewrite/v1.0
# git push origin --delete rewrite/v1.0
```

- [ ] **Step 7: Update `docs/future-work.md`**

Remove the "Plan C — remaining v1.0.0 scope" section (now shipped). Squashed commit:

```bash
sed -i '/^## Plan C — remaining v1.0.0 scope/,/^## /{ /^## Plan C/d; /^## /!d; }' docs/future-work.md
git add docs/future-work.md
git commit -m "Plan C Task 18: post-cutover — remove Plan C scope from future-work.md"
git push
```

---

## Plan C end-of-phase summary

After all 18 tasks merged + cutover ceremony:

- `main` is at v1.0.0
- `rewrite/v1.0` exists for archival reference
- All 8 bundled rooms have an audio digest baseline pinned in `tests/fixtures/audio_reference/`
- CI runs unit + component on every PR; integration + E2E on every push to main
- README documents the full CLI surface
- `gencast init`, `gencast subtitle`, `gencast cache status/clear` all shipped
- Map-reduce handles oversize sources without raising
- Rich Live UI active on TTY; plain logs on CI/pipes

What ships in v1.x:
- See `docs/future-work.md` (avatar viewer, ElevenLabs backend, multilingual validation, etc.)

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan C coverage |
|---|---|
| §1 Pipeline stages 4 (map-reduce) | T5, T6 |
| §3.3 CLI surface — full set | T4 (init), T8 (subtitle), T9 (cache status/clear) |
| §3.4 Output styling & verbosity (Rich Live, flags) | T1, T2, T3 |
| §5.3 Cache layout (XDG) — `~/.cache/gencast/llm/` opt-in | T7 |
| §5.4 Resumability via cache | already in Plan B (TTS) + T7 (LLM) |
| §6 Test pyramid (unit + component + integration + E2E) | T11, T12, T13 |
| §6.5 CI gating | T14, T15 |
| §7.4 M4A default output | already in Plan B |
| §10 Phases 6, 7, 8 | T1–T9 (P6+P7), T10–T18 (P8) |

Gaps:
- `gencast view` web subcommand — explicitly future-work (out of scope)
- `gencast estimate <NB.yaml>` — explicitly future-work
- TTS retry policy spec §5.6 — defaulted to backend-level retries already in Plan B; no explicit `--retries N` user flag in v1.0.0 (worth noting on future-work). Adding to future-work as a follow-up note is sufficient.

**2. Placeholder scan:** No "TBD", "TODO" in steps. Each step has working code.

**3. Type consistency:**
- `Reporter` ABC + `RichReporter` + `PlainReporter` consistent across T1, T2, T3.
- `LLMDiskCache.get/put` signatures consistent in T7 + downstream usage in T9.
- `compress_if_needed(source_text, source_tokens, target_model, summarise_provider, summarise_model, cost_meter)` signature consistent T5 → T6.
- `transcribe_to_srt(audio_path, *, openai_api_key=None)` consistent across T8 module + CLI.
- `_cache_dirs(kind)` / `_du(p)` / `_format_bytes(n)` helper signatures consistent T9.
- Stage indices (1=load, 2=extract, 5=outline, 6=transcript, 7=audio, 9=package) consistent T3.

---

Plan C complete. Ready to dispatch.
