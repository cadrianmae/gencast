# gencast v1.0 Plan B — transcript, TTS, audio FX, M4A packaging

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the rewrite from "outline-only preview" to "real `.m4a` end-to-end" — implement the per-segment transcript stage, pluggable TTS backends, the locked v1 audio-FX chain, native SRT subtitles, and ffmpeg M4A muxing.

**Architecture:** Each Plan B phase produces a more complete pipeline than the last. Phase 2 adds `state.transcript`. Phase 3 adds `state.combined_audio` (no spatial yet). Phase 4 routes audio through `audio_fx/` so it matches the v1 listening-test quality from the scratch harnesses. Phase 5 wires SRT + ffmpeg muxing and ships `gencast generate NB.yaml` end-to-end.

**Tech Stack:** LiteLLM (Anthropic prompt-cache passthrough), OpenAI SDK (TTS), httpx (Speaches OpenAI-compat), pydub + numpy + scipy (audio), Schroeder reverb, jinja2 (prompts), Click (CLI), ffmpeg subprocess (M4A mux with `mov_text`).

**Spec:** `docs/superpowers/specs/2026-05-07-gencast-v1-rewrite-design.md` — Sections 1, 2, 3.1-3.3, 4.x, 5, 7.2, 7.4, 7.5, 7.6, 10 (phases 2-5).

**Plan A handoff:** Trunk is `rewrite/v1.0` at commit `3e4f5aa`. `gencast preview NB.yaml` works end-to-end through the outline stage. Plan A established the contracts Plan B builds on:

- `gencast.pipeline.PodcastState` (fields: `notebook`, `resolved`, `source_text`, `source_tokens_*`, `outline`, `cost`)
- `gencast.pipeline.run_through_outline(notebook)` (Plan B replaces its callers but keeps it for `preview`)
- `gencast.llm.chat_completion(...)` returning `LLMResponse` and recording into `CostMeter`
- `gencast.cost.CostMeter` with `record_llm` and `record_tts`
- `gencast.profiles.schemas.Speaker / SpeakerProfile / EpisodeProfile / RoomProfile`
- `gencast.notebook.ResolvedNotebook` (briefing, models, basename, etc.)
- `gencast.logger.Reporter` ABC + `PlainReporter` (Rich variant comes in Plan C)
- `gencast.profiles.bundled/rooms/*.yaml` — 8 locked room presets

---

## Phase scope (this plan)

| Phase | Name | Tasks | Output at end |
|---|---|---|---|
| **2** | Transcript | T1–T5 | `state.transcript` populated; `transcript.json` writeable |
| **3** | TTS + bare audio combine | T6–T10 | first audible podcast as `<basename>.mp3` (no spatial yet) |
| **4** | audio_fx + room profile | T11–T15 | audio matches v1 listening-test quality |
| **5** | Subtitles + M4A mux + CLI | T16–T19 | `gencast generate NB.yaml` produces final `.m4a` w/ embedded subs |

Each phase ends in a runnable, testable demo against the bundled `revision-duo / exam-revision / small-room` profiles.

---

## Execution waves

Plan A used per-task git worktrees branched off `rewrite/v1.0`. Plan B does the same. Worktrees pre-created by the controller; subagents run with `cd <worktree-path>` and an explicit branch name.

| Wave | Trunk state at start | Tasks | Concurrency | Notes |
|---|---|---|---|---|
| **B0** | post-Plan-A trunk (`3e4f5aa`) | T1, T2 | 2-way | jinja+pydantic, cache_control helper — independent files |
| **B1** | post-B0 | T3 | 1-way | needs T1+T2 |
| **B2** | post-B1 | T4, T5 | 2-way | T4 = pipeline integration; T5 = JSON writer (independent files) |
| **B3** | post-B2 | T6, T9 | 2-way | TTS Protocol + cache (independent) |
| **B4** | post-B3 | T7, T8 | 2-way | OpenAI + Speaches backends (independent) |
| **B5** | post-B4 | T10 | 1-way | needs T6-T9 |
| **B6** | post-B5 | T11, T12, T13, T14 | 4-way | audio_fx leaf modules (all independent) |
| **B7** | post-B6 | T15 | 1-way | needs T11-T14, modifies pipeline/audio.py |
| **B8** | post-B7 | T16 | 1-way | subtitles |
| **B9** | post-B8 | T17 | 1-way | packaging (m4a mux) |
| **B10** | post-B9 | T18, T19 | 2-way | T18 = pipeline orchestrator; T19 = CLI generate command |

Sequential floor: 11 waves. The audio_fx phase (B6/B7) is where the parallelism pays off — four leaf modules implemented concurrently in B6, then assembled in B7.

### Branch naming

Each worktree branch follows: `rewrite/v1.0-taskB<N>-<short-slug>`. Examples:

- `rewrite/v1.0-taskB1-transcript-prompt`
- `rewrite/v1.0-taskB6-tts-base`
- `rewrite/v1.0-taskB11-pan-itd`

Merged into `rewrite/v1.0` with `--no-ff` to preserve task boundaries in history.

### Model assignments

(Haiku **replaces** Sonnet for boilerplate/lift work; never stacked before it.)

| Task | Implementer | Reasoning |
|---|---|---|
| T1 | sonnet | jinja prompt design + Pydantic with custom validators |
| T2 | sonnet | LiteLLM cache_control passthrough nuance |
| T3 | sonnet | per-segment LLM call with parsing + cost integration |
| T4 | sonnet | pipeline state extension + ordering |
| T5 | **haiku** | JSON writer — straight serialisation |
| T6 | sonnet | Protocol + sentence splitter + factory |
| T7, T8 | sonnet | TTS backends with retry + audio handling |
| T9 | **haiku** | sha256 disk cache — boilerplate |
| T10 | sonnet | asyncio.gather + clip timing + cost integration |
| T11–T14 | **haiku** | lifted verbatim from `scratch/` (boundary-tested already) |
| T15 | sonnet | room profile fan-out + integration into audio stage |
| T16 | sonnet | SRT format from clip timing |
| T17 | sonnet | ffmpeg subprocess + format dispatch |
| T18 | sonnet | full-pipeline orchestrator |
| T19 | sonnet | Click command + smoke test |

### Reviewer for every task

Single combined spec+quality review via `code-documentation:code-reviewer` agent (sonnet model) after each task's implementation lands.

---

## File Structure (Plan B)

| Path | Created/Modified | Responsibility |
|---|---|---|
| `gencast/prompts/transcript.jinja` | Created | Per-segment transcript prompt template |
| `gencast/pipeline/transcript.py` | Created | `Transcript`, `TranscriptTurn`, `run_transcript_stage` (per-segment loop with prompt cache) |
| `gencast/llm/caching.py` | Created | `with_cache_control(messages, last_n)` helper for Anthropic ephemeral cache |
| `gencast/pipeline/__init__.py` | Modified | Add transcript field to `PodcastState`; new `run_through_transcript`, `run_pipeline` |
| `gencast/pipeline/io.py` | Created | JSON writers: `write_transcript_json`, `write_outline_json`, `write_cost_json` |
| `gencast/tts/__init__.py` | Created | Re-exports + `get_backend(provider, model)` factory |
| `gencast/tts/base.py` | Created | `TTSBackend` Protocol; `split_sentences` |
| `gencast/tts/openai.py` | Created | `OpenAITTSBackend` (uses openai SDK) |
| `gencast/tts/speaches.py` | Created | `SpeachesTTSBackend` (httpx, OpenAI-compat) |
| `gencast/tts/cache.py` | Created | Disk-backed sha256 cache for TTS bytes |
| `gencast/pipeline/audio.py` | Created | Sentence-split, async TTS dispatch, per-clip FX, concat, ambience, normalize |
| `gencast/audio_fx/__init__.py` | Created | `apply_room(clip, speaker_idx, num_speakers, room)` orchestrator |
| `gencast/audio_fx/pan_itd.py` | Created | `pan_position`, `render_pan_itd` |
| `gencast/audio_fx/reverb.py` | Created | `SchroederReverb` (lifted from `scratch/spatial_test.py`) |
| `gencast/audio_fx/distance.py` | Created | `attenuate_for_distance` (lifted from `scratch/immersion_test.py`) |
| `gencast/audio_fx/ambience.py` | Created | `make_ambience_bed`, `mix_ambience` (lifted from `scratch/immersion_test.py`) |
| `gencast/audio_fx/normalize.py` | Created | `peak_normalize` |
| `gencast/audio_fx/_npbridge.py` | Created | `seg_to_np`, `np_to_seg` (lifted) |
| `gencast/pipeline/subtitles.py` | Created | `SrtEntry` + `build_native_srt` from clip timing |
| `gencast/pipeline/package.py` | Created | M4A mux via ffmpeg; mp3+srt sidecar; JSON sidecars |
| `gencast/cli/main.py` | Modified | Add `gencast generate NB.yaml` command + smoke fixture |
| `tests/component/test_transcript_stage.py` | Created | Mocked-LLM transcript stage tests |
| `tests/component/test_tts_backends.py` | Created | Backend tests with stub HTTP/SDK |
| `tests/component/test_audio_fx.py` | Created | Per-clip pipeline tests with synthetic input |
| `tests/component/test_subtitles.py` | Created | SRT formatting tests |
| `tests/component/test_package.py` | Created | ffmpeg mux test (gated on ffmpeg present) |
| `tests/component/test_pipeline_full.py` | Created | End-to-end mocked pipeline test |
| `tests/unit/test_llm_caching.py` | Created | cache_control insertion tests |
| `tests/unit/test_audio_fx_*.py` | Created | One unit test per leaf audio_fx module |
| `tests/fixtures/notebooks/smoke.yaml` | Created | Minimal 1-source notebook for B19 smoke test |

---

## Phase 2 — Transcript

### Task B1: Transcript jinja prompt + Pydantic models

**Files:**
- Create: `gencast/prompts/transcript.jinja`
- Create: `gencast/pipeline/transcript.py`
- Test: `tests/unit/test_transcript_models.py`

The transcript stage runs **once per outline segment**. The constant prefix (briefing + speakers + full source content + full outline) gets prompt-cached across segments 2..N. Only the per-segment instruction (segment name + size + neighbour context) varies.

The prompt yields JSON of shape `{"turns": [{"speaker": "Sophie", "text": "..."}, ...]}`. Each turn maps to a single speaker by name (must match `Speaker.name` in the speaker profile).

- [ ] **Step 1: Write the failing tests for the Pydantic models**

```python
# tests/unit/test_transcript_models.py
"""Pydantic model tests for Transcript / TranscriptTurn."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gencast.pipeline.transcript import Transcript, TranscriptTurn


def test_turn_minimal():
    t = TranscriptTurn(speaker="Sophie", text="Hello world.")
    assert t.speaker == "Sophie"
    assert t.text == "Hello world."
    assert t.segment_index is None  # set by stage executor, not by parser


def test_turn_rejects_empty_text():
    with pytest.raises(ValidationError):
        TranscriptTurn(speaker="Sophie", text="")


def test_turn_rejects_empty_speaker():
    with pytest.raises(ValidationError):
        TranscriptTurn(speaker="", text="Hi.")


def test_transcript_minimal():
    t = Transcript(turns=[
        TranscriptTurn(speaker="Sophie", text="Hi."),
        TranscriptTurn(speaker="Ben", text="Hello."),
    ])
    assert len(t.turns) == 2


def test_transcript_rejects_empty():
    with pytest.raises(ValidationError):
        Transcript(turns=[])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/unit/test_transcript_models.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `Transcript` and `TranscriptTurn`**

Create `gencast/pipeline/transcript.py`:

```python
"""Per-segment transcript stage — model + jinja rendering. Executor follows in Task B3."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

from gencast.pipeline.outline import OutlineSegment
from gencast.profiles.schemas import Speaker

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape(default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


class TranscriptTurn(BaseModel):
    """A single speaker turn in the podcast."""
    model_config = ConfigDict(extra="ignore")

    speaker: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    segment_index: int | None = None  # filled in by run_transcript_stage


class Transcript(BaseModel):
    """All turns from all segments, in delivery order."""
    model_config = ConfigDict(extra="ignore")

    turns: list[TranscriptTurn] = Field(..., min_length=1)


def render_transcript_segment_prompt(
    *,
    briefing: str,
    content: str,
    speakers: list[Speaker],
    outline_segments: list[OutlineSegment],
    segment_index: int,
    language: str | None,
) -> tuple[str, str]:
    """
    Render the transcript prompt as a (cacheable_prefix, per_segment_suffix) pair.

    The prefix is identical across all segments of one run (cache_write on segment 0,
    cache_read on segments 1..N-1). The suffix varies per segment.
    """
    prefix_tmpl = _jinja_env.get_template("transcript.jinja")
    prefix = prefix_tmpl.module.render_prefix(  # type: ignore[attr-defined]
        briefing=briefing,
        content=content,
        speakers=speakers,
        outline_segments=outline_segments,
        language=language,
    )
    suffix = prefix_tmpl.module.render_suffix(  # type: ignore[attr-defined]
        outline_segments=outline_segments,
        segment_index=segment_index,
    )
    return prefix, suffix
```

- [ ] **Step 4: Write the jinja template with two macros**

Create `gencast/prompts/transcript.jinja`:

```jinja
{% macro render_prefix(briefing, content, speakers, outline_segments, language) -%}
You are an AI podcast scriptwriter. Generate one segment of a multi-segment podcast.

<briefing>
{{ briefing }}
</briefing>

<source_content>
{{ content }}
</source_content>

<speakers>
{%- for speaker in speakers %}
- **{{ speaker.name }}**: {{ speaker.backstory }}
  Personality: {{ speaker.personality }}
{%- endfor %}
</speakers>

<full_outline>
{%- for seg in outline_segments %}
{{ loop.index }}. [{{ seg.size }}] {{ seg.name }} — {{ seg.description }}
{%- endfor %}
</full_outline>

{% if language -%}
LANGUAGE INSTRUCTION: Generate ALL output in {{ language }}.
{% endif -%}

Guidelines:
- Each turn is one speaker speaking. Alternate speakers naturally; don't force balance.
- Use only the speaker names listed above (case-sensitive). No "HOST1" / "HOST2".
- Don't restate "in this podcast we will..." or recap previous segments — segments are stitched contiguously.
- Match segment size: short ≈ 3 turns, medium ≈ 6 turns, long ≈ 10 turns.
- Speak naturally — contractions, mid-sentence shifts, occasional "yeah", "right". Avoid robotic exposition.
- Don't include sound effects, music cues, or stage directions.
{%- endmacro %}

{% macro render_suffix(outline_segments, segment_index) -%}
{% set current = outline_segments[segment_index] -%}
{% set total = outline_segments | length -%}

NOW WRITE: Segment {{ segment_index + 1 }} of {{ total }}: **{{ current.name }}** ({{ current.size }})

Description: {{ current.description }}

{% if segment_index == 0 -%}
This is the OPENING segment. Hosts greet the audience and introduce the topic.
{%- elif segment_index == total - 1 -%}
This is the CLOSING segment. Hosts wrap up and sign off.
{%- else -%}
This segment follows: "{{ outline_segments[segment_index - 1].name }}".
The next segment will be: "{{ outline_segments[segment_index + 1].name }}".
Bridge naturally from the prior topic into this one.
{%- endif %}

Return ONLY valid JSON in this exact shape, with no surrounding prose, no code fences:
{
  "turns": [
    {"speaker": "<one of the speaker names above>", "text": "<the turn>"}
  ]
}
{%- endmacro %}
```

- [ ] **Step 5: Run tests to verify Pydantic models pass**

Run: `./venv/bin/pytest tests/unit/test_transcript_models.py -v`
Expected: 5 tests pass.

- [ ] **Step 6: Smoke-test the jinja prefix/suffix render**

Run: `./venv/bin/python -c "
from gencast.pipeline.transcript import render_transcript_segment_prompt
from gencast.profiles.schemas import Speaker
from gencast.pipeline.outline import OutlineSegment
sp = [Speaker(name='Sophie', voice_id='nova', backstory='b', personality='p'),
      Speaker(name='Ben', voice_id='echo', backstory='b', personality='p')]
segs = [OutlineSegment(name='Intro', description='d', size='short'),
        OutlineSegment(name='Body', description='d', size='medium'),
        OutlineSegment(name='Wrap', description='d', size='short')]
prefix, suffix = render_transcript_segment_prompt(
    briefing='b', content='c', speakers=sp,
    outline_segments=segs, segment_index=1, language=None,
)
assert 'Sophie' in prefix and 'Ben' in prefix
assert 'Body' in suffix and '2 of 3' in suffix
assert 'follows' in suffix and 'Intro' in suffix and 'Wrap' in suffix
print('OK')
"`
Expected: prints `OK`.

- [ ] **Step 7: Commit**

```bash
git add gencast/prompts/transcript.jinja gencast/pipeline/transcript.py tests/unit/test_transcript_models.py
git commit -m "Plan B Task 1: transcript jinja + Transcript/TranscriptTurn pydantic models"
```

---

### Task B2: Anthropic prompt-cache helper

**Files:**
- Create: `gencast/llm/caching.py`
- Test: `tests/unit/test_llm_caching.py`

LiteLLM passes `cache_control` blocks straight through to the Anthropic API. The cache marks the *last* content block of a message with `{"type": "ephemeral"}`. We want the briefing+content+outline prefix cached, so we pass the prefix as one user message ending in a cache_control marker, and the per-segment suffix as a follow-up user message.

For non-Anthropic providers, the helper degrades to a passthrough (just produces a single user message with prefix+suffix concatenated).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_llm_caching.py
"""Tests for cache_control message construction."""

from __future__ import annotations

from gencast.llm.caching import build_cached_messages


def test_anthropic_marks_prefix_with_cache_control():
    msgs = build_cached_messages(
        provider="anthropic", prefix="PREFIX_TEXT", suffix="SUFFIX_TEXT",
    )
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["role"] == "user"
    parts = msg["content"]
    assert isinstance(parts, list)
    assert len(parts) == 2
    assert parts[0]["type"] == "text"
    assert parts[0]["text"] == "PREFIX_TEXT"
    assert parts[0]["cache_control"] == {"type": "ephemeral"}
    assert parts[1]["type"] == "text"
    assert parts[1]["text"] == "SUFFIX_TEXT"
    assert "cache_control" not in parts[1]


def test_non_anthropic_uses_plain_string():
    msgs = build_cached_messages(
        provider="openai", prefix="PREFIX", suffix="SUFFIX",
    )
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "PREFIX\n\nSUFFIX"


def test_anthropic_empty_suffix_still_two_blocks():
    msgs = build_cached_messages(
        provider="anthropic", prefix="P", suffix="",
    )
    parts = msgs[0]["content"]
    assert len(parts) == 2
    assert parts[1]["text"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/unit/test_llm_caching.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `build_cached_messages`**

```python
# gencast/llm/caching.py
"""Anthropic ephemeral prompt-cache helper.

LiteLLM passes `cache_control` blocks straight through to Anthropic. For other
providers we emit a plain string (LiteLLM ignores cache_control on them, but
content-list shape is not always supported, so we play safe).
"""

from __future__ import annotations

from typing import Any


def build_cached_messages(
    *, provider: str, prefix: str, suffix: str,
) -> list[dict[str, Any]]:
    """
    Build a single-user-message payload that caches `prefix` for Anthropic.

    On Anthropic the message uses content-list form with a cache_control marker
    on the prefix block. On other providers we concatenate prefix+suffix into a
    plain string for maximum compatibility.
    """
    if provider == "anthropic":
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prefix,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": suffix},
                ],
            }
        ]
    return [{"role": "user", "content": f"{prefix}\n\n{suffix}"}]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/unit/test_llm_caching.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/llm/caching.py tests/unit/test_llm_caching.py
git commit -m "Plan B Task 2: build_cached_messages helper for Anthropic ephemeral cache"
```

---

### Task B3: Transcript stage executor (per-segment LLM loop)

**Files:**
- Modify: `gencast/pipeline/transcript.py` (append `run_transcript_stage`)
- Test: `tests/component/test_transcript_stage.py`

Stage logic: for each outline segment, call the LLM with the cached prefix + per-segment suffix, parse the JSON, validate every turn's speaker name is in the profile, tag each turn with `segment_index`, and accumulate into a single `Transcript`.

Cost: one entry under stage `"transcript"` (`record_llm` accumulates across calls).

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_transcript_stage.py
"""Component tests for the per-segment transcript stage with mocked LLM."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.pipeline.outline import Outline, OutlineSegment
from gencast.pipeline.transcript import (
    Transcript,
    TranscriptTurn,
    run_transcript_stage,
)
from gencast.profiles.schemas import Speaker


@pytest.fixture
def speakers():
    return [
        Speaker(name="Sophie", voice_id="nova", backstory="bg", personality="p"),
        Speaker(name="Ben", voice_id="echo", backstory="bg", personality="p"),
    ]


@pytest.fixture
def outline():
    return Outline(segments=[
        OutlineSegment(name="Intro", description="d", size="short"),
        OutlineSegment(name="Body", description="d", size="medium"),
        OutlineSegment(name="Wrap", description="d", size="short"),
    ])


def _mock_response(json_str: str):
    resp = MagicMock()
    resp.content = json_str
    return resp


def test_run_transcript_stage_loops_segments(speakers, outline, cost_meter):
    """3 segments → 3 LLM calls → 3 transcripts concatenated."""
    seg_responses = [
        '{"turns":[{"speaker":"Sophie","text":"Hi all."},{"speaker":"Ben","text":"Hello."}]}',
        '{"turns":[{"speaker":"Sophie","text":"Body 1."},{"speaker":"Ben","text":"Body 2."}]}',
        '{"turns":[{"speaker":"Ben","text":"Bye."}]}',
    ]
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.side_effect = [_mock_response(s) for s in seg_responses]
        transcript = run_transcript_stage(
            briefing="b", content="c",
            speakers=speakers, outline=outline, language=None,
            transcript_provider="anthropic",
            transcript_model="claude-sonnet-4",
            cost_meter=cost_meter,
        )
    assert isinstance(transcript, Transcript)
    assert len(transcript.turns) == 5
    assert mock.call_count == 3
    # Segment index annotation
    assert transcript.turns[0].segment_index == 0
    assert transcript.turns[2].segment_index == 1
    assert transcript.turns[4].segment_index == 2


def test_run_transcript_stage_records_cost_per_call(speakers, outline, cost_meter):
    one = '{"turns":[{"speaker":"Sophie","text":"x"}]}'
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.return_value = _mock_response(one)
        run_transcript_stage(
            briefing="b", content="c",
            speakers=speakers, outline=outline, language=None,
            transcript_provider="anthropic",
            transcript_model="claude-sonnet-4",
            cost_meter=cost_meter,
        )
    # All three calls record under the same "transcript" stage
    for call in mock.call_args_list:
        assert call.kwargs["stage"] == "transcript"
        assert call.kwargs["cost_meter"] is cost_meter


def test_run_transcript_stage_uses_cache_control_for_anthropic(speakers, outline, cost_meter):
    one = '{"turns":[{"speaker":"Sophie","text":"x"}]}'
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.return_value = _mock_response(one)
        run_transcript_stage(
            briefing="b", content="c",
            speakers=speakers, outline=outline, language=None,
            transcript_provider="anthropic",
            transcript_model="claude-sonnet-4",
            cost_meter=cost_meter,
        )
    # First call should have cache_control marker
    first_msgs = mock.call_args_list[0].kwargs["messages"]
    parts = first_msgs[0]["content"]
    assert isinstance(parts, list)
    assert parts[0].get("cache_control") == {"type": "ephemeral"}


def test_run_transcript_stage_rejects_unknown_speaker(speakers, outline, cost_meter):
    bad = '{"turns":[{"speaker":"Charlie","text":"hi"}]}'
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.return_value = _mock_response(bad)
        with pytest.raises(ValueError, match="unknown speaker"):
            run_transcript_stage(
                briefing="b", content="c",
                speakers=speakers, outline=outline, language=None,
                transcript_provider="anthropic",
                transcript_model="claude-sonnet-4",
                cost_meter=cost_meter,
            )


def test_run_transcript_stage_handles_code_fence(speakers, outline, cost_meter):
    fenced = '```json\n{"turns":[{"speaker":"Sophie","text":"hi"}]}\n```'
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.return_value = _mock_response(fenced)
        transcript = run_transcript_stage(
            briefing="b", content="c",
            speakers=speakers, outline=outline, language=None,
            transcript_provider="anthropic",
            transcript_model="claude-sonnet-4",
            cost_meter=cost_meter,
        )
    assert transcript.turns[0].text == "hi"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/component/test_transcript_stage.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `run_transcript_stage`**

Append to `gencast/pipeline/transcript.py`:

```python
import json
import re

from gencast.cost import CostMeter
from gencast.llm import chat_completion
from gencast.llm.caching import build_cached_messages
from gencast.pipeline.outline import Outline


# Same code-fence stripper as outline stage. Keep local to avoid cross-module import cycle.
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_code_fence(s: str) -> str:
    m = _FENCE_RE.match(s)
    return m.group(1) if m else s


def run_transcript_stage(
    *,
    briefing: str,
    content: str,
    speakers: list[Speaker],
    outline: Outline,
    language: str | None,
    transcript_provider: str,
    transcript_model: str,
    cost_meter: CostMeter,
) -> Transcript:
    """Loop outline segments, one LLM call each, accumulate turns into a Transcript."""
    valid_speaker_names = {s.name for s in speakers}
    all_turns: list[TranscriptTurn] = []

    for seg_index in range(len(outline.segments)):
        prefix, suffix = render_transcript_segment_prompt(
            briefing=briefing, content=content, speakers=speakers,
            outline_segments=outline.segments, segment_index=seg_index,
            language=language,
        )
        messages = build_cached_messages(
            provider=transcript_provider, prefix=prefix, suffix=suffix,
        )
        response = chat_completion(
            provider=transcript_provider,
            model=transcript_model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=5000,
            cost_meter=cost_meter,
            stage="transcript",
        )

        raw = _strip_code_fence(response.content)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Transcript segment {seg_index} returned non-JSON: {e}. "
                f"Raw: {raw[:300]!r}"
            ) from e

        seg_turns_raw = data.get("turns")
        if not isinstance(seg_turns_raw, list) or not seg_turns_raw:
            raise ValueError(
                f"Transcript segment {seg_index} returned no turns: {data!r}"
            )

        for t in seg_turns_raw:
            turn = TranscriptTurn(speaker=t["speaker"], text=t["text"])
            if turn.speaker not in valid_speaker_names:
                raise ValueError(
                    f"Transcript segment {seg_index} produced unknown speaker "
                    f"{turn.speaker!r}; valid: {sorted(valid_speaker_names)}"
                )
            turn.segment_index = seg_index
            all_turns.append(turn)

    return Transcript(turns=all_turns)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/component/test_transcript_stage.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/transcript.py tests/component/test_transcript_stage.py
git commit -m "Plan B Task 3: run_transcript_stage with per-segment loop + cache_control + speaker validation"
```

---

### Task B4: Pipeline integration — `run_through_transcript`

**Files:**
- Modify: `gencast/pipeline/__init__.py`
- Test: `tests/component/test_pipeline_through_transcript.py`

Add `transcript: Transcript | None = None` to `PodcastState`. Add a new orchestrator `run_through_transcript` that runs the full Plan A pipeline (resolve → extract → preflight → outline) **plus** the transcript stage. Keep `run_through_outline` as-is for the `preview` command.

- [ ] **Step 1: Write the failing test**

```python
# tests/component/test_pipeline_through_transcript.py
"""Smoke test for run_through_transcript with mocked LLM calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.notebook import Notebook
from gencast.pipeline import PodcastState, run_through_transcript


@pytest.fixture
def smoke_notebook(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("# Sample\n\nSome content.\n")
    return Notebook(
        title="Smoke",
        sources=[str(src)],
        speaker_profile="revision-duo",
        episode_profile="exam-revision",
        room_profile="small-room",
    )


def _mock_llm(content: str):
    r = MagicMock()
    r.content = content
    return r


def test_run_through_transcript_populates_state(smoke_notebook):
    outline_json = '{"segments":[{"name":"Intro","description":"d","size":"short"},{"name":"Wrap","description":"d","size":"short"}]}'
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hi."},{"speaker":"Ben","text":"Hello."}]}'

    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx:
        mock_ol.return_value = _mock_llm(outline_json)
        mock_tx.return_value = _mock_llm(seg_json)

        state = run_through_transcript(smoke_notebook)

    assert isinstance(state, PodcastState)
    assert state.outline is not None
    assert len(state.outline.segments) == 2
    assert state.transcript is not None
    assert len(state.transcript.turns) == 4  # 2 segments × 2 turns each
    # transcript stage was called once per segment
    assert mock_tx.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/component/test_pipeline_through_transcript.py -v`
Expected: FAIL with `ImportError` (`run_through_transcript` does not exist).

- [ ] **Step 3: Modify `gencast/pipeline/__init__.py`**

Replace contents of `gencast/pipeline/__init__.py` with:

```python
"""Pipeline state + orchestrators. Plan B extends through the transcript stage."""

from __future__ import annotations

from dataclasses import dataclass, field

from gencast.cost import CostMeter
from gencast.notebook import Notebook, ResolvedNotebook, resolve_notebook
from gencast.pipeline.extract import extract_sources
from gencast.pipeline.outline import Outline, run_outline_stage
from gencast.pipeline.preflight import preflight
from gencast.pipeline.transcript import Transcript, run_transcript_stage


@dataclass
class PodcastState:
    notebook: Notebook
    resolved: ResolvedNotebook
    source_text: str = ""
    source_tokens_original: int = 0
    source_tokens_final: int = 0
    outline: Outline | None = None
    transcript: Transcript | None = None
    cost: CostMeter = field(default_factory=CostMeter)


def _run_load_extract_preflight_outline(notebook: Notebook) -> PodcastState:
    """Stages 1, 2, 3, 5. (4 = map-reduce, deferred to Plan C.)"""
    resolved = resolve_notebook(notebook)
    state = PodcastState(notebook=notebook, resolved=resolved)

    text, tokens = extract_sources(
        notebook.sources,
        model=f"{resolved.outline_provider}/{resolved.outline_model}",
    )
    state.source_text = text
    state.source_tokens_original = tokens
    state.source_tokens_final = tokens

    preflight(
        source_tokens=tokens,
        model=f"{resolved.outline_provider}/{resolved.outline_model}",
    )

    state.outline = run_outline_stage(
        briefing=resolved.briefing,
        content=text,
        speakers=resolved.speaker.speakers,
        num_segments=resolved.num_segments,
        language=resolved.episode.language,
        outline_provider=resolved.outline_provider,
        outline_model=resolved.outline_model,
        cost_meter=state.cost,
    )
    return state


def run_through_outline(notebook: Notebook) -> PodcastState:
    """Plan A pipeline: load → extract → preflight → outline. Used by `gencast preview`."""
    return _run_load_extract_preflight_outline(notebook)


def run_through_transcript(notebook: Notebook) -> PodcastState:
    """Plan A pipeline + transcript stage. Used by Plan B/C orchestrators."""
    state = _run_load_extract_preflight_outline(notebook)
    assert state.outline is not None  # populated above
    state.transcript = run_transcript_stage(
        briefing=state.resolved.briefing,
        content=state.source_text,
        speakers=state.resolved.speaker.speakers,
        outline=state.outline,
        language=state.resolved.episode.language,
        transcript_provider=state.resolved.transcript_provider,
        transcript_model=state.resolved.transcript_model,
        cost_meter=state.cost,
    )
    return state
```

- [ ] **Step 4: Run test to verify it passes (and existing tests still pass)**

Run: `./venv/bin/pytest tests/component/test_pipeline_through_transcript.py tests/component/test_pipeline_through_outline.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/__init__.py tests/component/test_pipeline_through_transcript.py
git commit -m "Plan B Task 4: PodcastState.transcript + run_through_transcript orchestrator"
```

---

### Task B5: JSON output writers

**Files:**
- Create: `gencast/pipeline/io.py`
- Test: `tests/unit/test_pipeline_io.py`

JSON sidecars per spec §3.2: `<basename>.transcript.json`, `<basename>.outline.json`, `<basename>.cost.json`. Used in Plan B by Task B17 packaging.

`transcript.json` shape (spec §3.2):

```json
{
  "title": "...",
  "speakers": ["Sophie", "Ben"],
  "duration_ms": 0,           // 0 if audio not yet rendered
  "turns": [
    {"speaker": "Sophie", "text": "...", "segment_index": 0, "start_ms": 0, "end_ms": 0}
  ]
}
```

Plan B writes `start_ms` / `end_ms` after audio generation (set on the clips); JSON writer reads from `state.clips` if present, else 0/0.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_pipeline_io.py
"""JSON sidecar writers."""

from __future__ import annotations

import json

from gencast.pipeline.io import (
    write_cost_json,
    write_outline_json,
    write_transcript_json,
)


def test_write_outline_json(tmp_path, sample_state_with_outline):
    p = tmp_path / "out.outline.json"
    write_outline_json(sample_state_with_outline, p)
    data = json.loads(p.read_text())
    assert data["title"] == sample_state_with_outline.notebook.title
    assert len(data["segments"]) == 2
    assert data["segments"][0]["name"] == "Intro"


def test_write_transcript_json(tmp_path, sample_state_with_transcript):
    p = tmp_path / "out.transcript.json"
    write_transcript_json(sample_state_with_transcript, p)
    data = json.loads(p.read_text())
    assert data["title"] == sample_state_with_transcript.notebook.title
    assert data["speakers"] == ["Sophie", "Ben"]
    assert data["duration_ms"] == 0  # no clips yet
    assert len(data["turns"]) == 2
    assert data["turns"][0]["speaker"] == "Sophie"
    assert data["turns"][0]["segment_index"] == 0


def test_write_cost_json(tmp_path, sample_state_with_outline):
    sample_state_with_outline.cost.record_llm(
        "outline", model="anthropic/claude-haiku-4.5",
        tokens_in=100, tokens_out=20, usd=0.001,
    )
    p = tmp_path / "out.cost.json"
    write_cost_json(sample_state_with_outline, p)
    data = json.loads(p.read_text())
    assert "stages" in data
    assert "outline" in data["stages"]
    assert data["total_usd"] > 0
```

Add fixtures to `tests/conftest.py` (append):

```python
from gencast.notebook import Notebook, ResolvedNotebook
from gencast.pipeline import PodcastState
from gencast.pipeline.outline import Outline, OutlineSegment
from gencast.pipeline.transcript import Transcript, TranscriptTurn
from gencast.profiles.schemas import (
    EpisodeProfile, RoomProfile, Speaker, SpeakerProfile,
)


def _resolved_for_smoke():
    sp = SpeakerProfile(
        name="revision-duo", tts_provider="openai", tts_model="tts-1-hd",
        speakers=[
            Speaker(name="Sophie", voice_id="nova", backstory="b", personality="p"),
            Speaker(name="Ben", voice_id="echo", backstory="b", personality="p"),
        ],
    )
    ep = EpisodeProfile(name="exam-revision", default_briefing="b")
    rm = RoomProfile(name="small-room")
    nb = Notebook(title="Smoke", sources=["dummy.md"])
    return ResolvedNotebook(
        notebook=nb, speaker=sp, episode=ep, room=rm,
        briefing="b",
        outline_provider="anthropic", outline_model="claude-haiku-4.5",
        transcript_provider="anthropic", transcript_model="claude-sonnet-4",
        num_segments=2, basename="smoke",
    )


@pytest.fixture
def sample_state_with_outline():
    resolved = _resolved_for_smoke()
    state = PodcastState(notebook=resolved.notebook, resolved=resolved)
    state.outline = Outline(segments=[
        OutlineSegment(name="Intro", description="d", size="short"),
        OutlineSegment(name="Wrap", description="d", size="short"),
    ])
    return state


@pytest.fixture
def sample_state_with_transcript(sample_state_with_outline):
    state = sample_state_with_outline
    t1 = TranscriptTurn(speaker="Sophie", text="Hi.")
    t1.segment_index = 0
    t2 = TranscriptTurn(speaker="Ben", text="Bye.")
    t2.segment_index = 1
    state.transcript = Transcript(turns=[t1, t2])
    return state
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/unit/test_pipeline_io.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `gencast/pipeline/io.py`**

```python
"""JSON sidecar writers — outline.json, transcript.json, cost.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gencast.pipeline import PodcastState


def write_outline_json(state: "PodcastState", path: Path) -> None:
    assert state.outline is not None, "outline must be populated before writing JSON"
    payload = {
        "title": state.notebook.title,
        "segments": [
            {"name": s.name, "description": s.description, "size": s.size}
            for s in state.outline.segments
        ],
    }
    path.write_text(json.dumps(payload, indent=2))


def write_transcript_json(state: "PodcastState", path: Path) -> None:
    assert state.transcript is not None, "transcript must be populated before writing JSON"
    duration_ms = 0
    clips = getattr(state, "clips", None)
    if clips:
        duration_ms = max(c.end_ms for c in clips)

    turn_payloads = []
    for i, t in enumerate(state.transcript.turns):
        start_ms = end_ms = 0
        if clips and i < len(clips):
            start_ms = clips[i].start_ms
            end_ms = clips[i].end_ms
        turn_payloads.append({
            "speaker": t.speaker,
            "text": t.text,
            "segment_index": t.segment_index,
            "start_ms": start_ms,
            "end_ms": end_ms,
        })

    payload = {
        "title": state.notebook.title,
        "speakers": [s.name for s in state.resolved.speaker.speakers],
        "duration_ms": duration_ms,
        "turns": turn_payloads,
    }
    path.write_text(json.dumps(payload, indent=2))


def write_cost_json(state: "PodcastState", path: Path) -> None:
    path.write_text(json.dumps(state.cost.to_dict(), indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/unit/test_pipeline_io.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/io.py tests/unit/test_pipeline_io.py tests/conftest.py
git commit -m "Plan B Task 5: JSON writers for outline, transcript, cost sidecars"
```

---

## Phase 3 — TTS + bare audio combine

### Task B6: TTS Protocol + sentence splitter + factory

**Files:**
- Create: `gencast/tts/__init__.py`
- Create: `gencast/tts/base.py`
- Test: `tests/unit/test_tts_base.py`

The Protocol defines a tiny surface so backends are swappable. `synthesize` is async because Phase 3's audio stage gathers concurrent calls; sync wrappers can call `asyncio.run` if needed.

`split_sentences` is lifted verbatim from `scratch/spatial_test.py:163` (boundary-tested in `scratch/boundary_test.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_tts_base.py
"""TTSBackend Protocol and sentence splitter."""

from __future__ import annotations

from gencast.tts.base import TTSBackend, split_sentences


def test_split_simple():
    s = split_sentences("Hello there. How are you? I am well!")
    assert s == ["Hello there.", "How are you?", "I am well!"]


def test_split_no_terminator():
    s = split_sentences("just some text without ending")
    assert s == ["just some text without ending"]


def test_split_empty_returns_single():
    s = split_sentences("")
    assert s == [""]  # contract: never returns empty list


def test_split_quoted_continuation():
    """Sentence boundary requires capital or quote after the gap."""
    s = split_sentences('She said "Hi." Then she left.')
    assert len(s) == 2


def test_protocol_check():
    """A minimal backend satisfies the Protocol."""

    class StubBackend:
        async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
            return b"\x00\x00", 1.0

        @property
        def usd_per_audio_second(self) -> float:
            return 0.0

        @property
        def backend_name(self) -> str:
            return "stub"

        @property
        def model(self) -> str:
            return "stub-1"

    b: TTSBackend = StubBackend()  # type-check at runtime
    assert b.backend_name == "stub"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/unit/test_tts_base.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `gencast/tts/base.py`**

```python
"""TTSBackend Protocol + sentence splitter shared across backends."""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

# Lifted verbatim from scratch/spatial_test.py — boundary cases vetted there.
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences. Always returns at least one element."""
    parts = [p.strip() for p in _SENT_RE.split(text) if p.strip()]
    return parts or [text]


@runtime_checkable
class TTSBackend(Protocol):
    """Minimal surface every TTS backend implements.

    Returns mp3 bytes (not wav, not pydub) so caches can store the raw stream
    untouched. Audio loaders convert via pydub later.
    """

    @property
    def backend_name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def usd_per_audio_second(self) -> float: ...

    async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
        """Return (mp3_bytes, audio_seconds)."""
        ...
```

- [ ] **Step 4: Implement `gencast/tts/__init__.py` with the factory**

```python
"""TTS package — factory + Protocol re-export."""

from __future__ import annotations

from gencast.tts.base import TTSBackend, split_sentences


def get_backend(provider: str, model: str, **config: object) -> TTSBackend:
    """Resolve a TTSBackend by provider name. Imports lazily to keep startup fast."""
    if provider == "openai":
        from gencast.tts.openai import OpenAITTSBackend
        return OpenAITTSBackend(model=model, **config)  # type: ignore[arg-type]
    if provider == "speaches":
        from gencast.tts.speaches import SpeachesTTSBackend
        return SpeachesTTSBackend(model=model, **config)  # type: ignore[arg-type]
    raise ValueError(f"Unknown TTS provider: {provider!r}")


__all__ = ["TTSBackend", "get_backend", "split_sentences"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/unit/test_tts_base.py -v`
Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add gencast/tts/__init__.py gencast/tts/base.py tests/unit/test_tts_base.py
git commit -m "Plan B Task 6: TTSBackend Protocol + split_sentences + get_backend factory"
```

---

### Task B7: OpenAI TTS backend

**Files:**
- Create: `gencast/tts/openai.py`
- Test: `tests/component/test_tts_openai.py`

OpenAI uses `client.audio.speech.with_streaming_response.create(...)` returning chunked bytes. We collect them into memory (clips are short, ≤ ~30s) and measure duration via pydub. `tts-1-hd` pricing per OpenAI: $0.030 / 1K characters; we record audio_seconds on the cost meter and the USD.

(OpenAI's TTS API does not return token usage; spec records by audio-seconds for both backends.)

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_tts_openai.py
"""OpenAI TTS backend with mocked SDK."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from gencast.tts.openai import OpenAITTSBackend


@pytest.fixture
def fake_mp3_bytes():
    """A minimal valid silent mp3 frame (~64 ms). pydub can decode it."""
    # 32 bytes of MPEG-1 Layer III silence header. pydub will load via ffmpeg.
    # Use real silence file in the repo if available; here we pre-render via pydub at test time.
    from pydub import AudioSegment
    seg = AudioSegment.silent(duration=200, frame_rate=24000).set_channels(1)
    import io
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="64k")
    return buf.getvalue()


def _mock_streaming_response(payload: bytes):
    """Mimic openai's with_streaming_response.create context manager."""
    cm = MagicMock()

    def stream_to_file(path):
        from pathlib import Path
        Path(path).write_bytes(payload)

    cm.__enter__.return_value.stream_to_file = stream_to_file
    cm.__exit__.return_value = False
    return cm


def test_openai_tts_returns_bytes_and_seconds(fake_mp3_bytes):
    with patch("gencast.tts.openai.OpenAI") as openai_cls:
        client = openai_cls.return_value
        client.audio.speech.with_streaming_response.create.return_value = (
            _mock_streaming_response(fake_mp3_bytes)
        )

        backend = OpenAITTSBackend(model="tts-1-hd")
        audio_bytes, seconds = asyncio.run(
            backend.synthesize(voice="nova", text="Hello.")
        )
    assert audio_bytes == fake_mp3_bytes
    assert 0.1 < seconds < 0.5


def test_openai_tts_backend_metadata():
    with patch("gencast.tts.openai.OpenAI"):
        backend = OpenAITTSBackend(model="tts-1-hd")
    assert backend.backend_name == "openai"
    assert backend.model == "tts-1-hd"
    # tts-1-hd pricing: $0.030 / 1K chars ≈ $0.000234 / second @ 128 chars/sec speaking rate.
    # We only assert it is positive — exact rate not load-bearing.
    assert backend.usd_per_audio_second > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/component/test_tts_openai.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `gencast/tts/openai.py`**

```python
"""OpenAI TTS backend (tts-1, tts-1-hd)."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from openai import OpenAI
from pydub import AudioSegment

# OpenAI tts-1-hd pricing as of 2026: $0.030 / 1K input characters.
# At ~128 chars/sec speaking rate this is ~$0.000234 / audio second.
# We approximate via audio_seconds for cost-meter compatibility.
_USD_PER_SEC = {
    "tts-1": 0.000117,
    "tts-1-hd": 0.000234,
}


class OpenAITTSBackend:
    """Synchronous OpenAI client wrapped in async surface (offload via asyncio.to_thread)."""

    def __init__(self, *, model: str = "tts-1-hd", api_key: str | None = None):
        self._model = model
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    @property
    def backend_name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    @property
    def usd_per_audio_second(self) -> float:
        return _USD_PER_SEC.get(self._model, 0.000234)

    async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
        import asyncio
        return await asyncio.to_thread(self._synthesize_blocking, voice, text)

    def _synthesize_blocking(self, voice: str, text: str) -> tuple[bytes, float]:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp = Path(f.name)
        try:
            with self._client.audio.speech.with_streaming_response.create(
                model=self._model, voice=voice, input=text,
            ) as resp:
                resp.stream_to_file(str(tmp))
            audio_bytes = tmp.read_bytes()
            seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
            seconds = len(seg) / 1000.0
            return audio_bytes, seconds
        finally:
            tmp.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/component/test_tts_openai.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/tts/openai.py tests/component/test_tts_openai.py
git commit -m "Plan B Task 7: OpenAITTSBackend (tts-1-hd) with async wrapper"
```

---

### Task B8: Speaches TTS backend (OpenAI-compat)

**Files:**
- Create: `gencast/tts/speaches.py`
- Test: `tests/component/test_tts_speaches.py`

Speaches is a self-hosted OpenAI-compatible inference server (commonly serving Kokoro). Endpoint: `POST {base_url}/v1/audio/speech` with JSON `{"model": ..., "voice": ..., "input": ...}`. Returns mp3 bytes.

We use `httpx.AsyncClient` directly (no SDK dependency). Local runs are usually free → `usd_per_audio_second = 0.0`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_tts_speaches.py
"""Speaches TTS backend with mocked httpx."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gencast.tts.speaches import SpeachesTTSBackend


@pytest.fixture
def fake_mp3_bytes():
    from pydub import AudioSegment
    seg = AudioSegment.silent(duration=300, frame_rate=24000).set_channels(1)
    import io
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="64k")
    return buf.getvalue()


def test_speaches_synthesize_calls_speech_endpoint(fake_mp3_bytes):
    response = MagicMock()
    response.status_code = 200
    response.content = fake_mp3_bytes
    response.raise_for_status = MagicMock()

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client_cm)
    client_cm.__aexit__ = AsyncMock(return_value=False)
    client_cm.post = AsyncMock(return_value=response)

    with patch("gencast.tts.speaches.httpx.AsyncClient", return_value=client_cm):
        backend = SpeachesTTSBackend(model="kokoro", base_url="http://localhost:8000")
        audio_bytes, seconds = asyncio.run(
            backend.synthesize(voice="af_alloy", text="Hi.")
        )

    assert audio_bytes == fake_mp3_bytes
    assert seconds > 0.2
    call = client_cm.post.await_args
    assert call.args[0].endswith("/v1/audio/speech")
    body = call.kwargs["json"]
    assert body["model"] == "kokoro"
    assert body["voice"] == "af_alloy"
    assert body["input"] == "Hi."


def test_speaches_metadata():
    backend = SpeachesTTSBackend(model="kokoro")
    assert backend.backend_name == "speaches"
    assert backend.model == "kokoro"
    assert backend.usd_per_audio_second == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/component/test_tts_speaches.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `gencast/tts/speaches.py`**

```python
"""Speaches TTS backend — OpenAI-compatible endpoint, httpx-based."""

from __future__ import annotations

import io
import os

import httpx
from pydub import AudioSegment


class SpeachesTTSBackend:
    """POST /v1/audio/speech to a Speaches-compatible server."""

    def __init__(
        self,
        *,
        model: str = "kokoro",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        self._model = model
        self._base_url = (base_url or os.environ.get("SPEACHES_BASE_URL")
                         or "http://localhost:8000").rstrip("/")
        self._api_key = api_key or os.environ.get("SPEACHES_API_KEY") or ""
        self._timeout = timeout

    @property
    def backend_name(self) -> str:
        return "speaches"

    @property
    def model(self) -> str:
        return self._model

    @property
    def usd_per_audio_second(self) -> float:
        return 0.0  # Self-hosted by default; if using a paid Speaches host, override here.

    async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
        url = f"{self._base_url}/v1/audio/speech"
        body = {"model": self._model, "voice": voice, "input": text, "response_format": "mp3"}
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            audio_bytes = resp.content

        seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        seconds = len(seg) / 1000.0
        return audio_bytes, seconds
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/component/test_tts_speaches.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/tts/speaches.py tests/component/test_tts_speaches.py
git commit -m "Plan B Task 8: SpeachesTTSBackend (OpenAI-compat httpx)"
```

---

### Task B9: TTS disk cache

**Files:**
- Create: `gencast/tts/cache.py`
- Test: `tests/unit/test_tts_cache.py`

Cache key is `sha256((provider, model, voice, text))[:24]`. Files stored under `~/.cache/gencast/tts/<provider>/<model>/<voice>/<key>.mp3`. Hit returns cached bytes; miss returns `None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_tts_cache.py
"""TTS disk cache — sha256 keying, miss/hit semantics."""

from __future__ import annotations

from gencast.tts.cache import TTSDiskCache


def test_miss_returns_none(tmp_path):
    cache = TTSDiskCache(tmp_path)
    assert cache.get(provider="openai", model="tts-1-hd", voice="nova", text="hello") is None


def test_hit_after_put(tmp_path):
    cache = TTSDiskCache(tmp_path)
    payload = b"\x00\x01\x02\x03"
    cache.put(provider="openai", model="tts-1-hd", voice="nova", text="hi", audio_bytes=payload)
    got = cache.get(provider="openai", model="tts-1-hd", voice="nova", text="hi")
    assert got == payload


def test_different_text_misses(tmp_path):
    cache = TTSDiskCache(tmp_path)
    cache.put(provider="openai", model="tts-1-hd", voice="nova", text="A", audio_bytes=b"a")
    assert cache.get(provider="openai", model="tts-1-hd", voice="nova", text="B") is None


def test_different_voice_misses(tmp_path):
    cache = TTSDiskCache(tmp_path)
    cache.put(provider="openai", model="tts-1-hd", voice="nova", text="A", audio_bytes=b"a")
    assert cache.get(provider="openai", model="tts-1-hd", voice="echo", text="A") is None


def test_layout(tmp_path):
    cache = TTSDiskCache(tmp_path)
    cache.put(provider="openai", model="tts-1-hd", voice="nova", text="A", audio_bytes=b"a")
    files = list(tmp_path.rglob("*.mp3"))
    assert len(files) == 1
    rel = files[0].relative_to(tmp_path)
    assert rel.parts[0] == "openai"
    assert rel.parts[1] == "tts-1-hd"
    assert rel.parts[2] == "nova"
    assert rel.parts[3].endswith(".mp3")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/unit/test_tts_cache.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `gencast/tts/cache.py`**

```python
"""Disk-backed TTS cache (always on; deterministic + expensive workload)."""

from __future__ import annotations

import hashlib
from pathlib import Path


class TTSDiskCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, *, provider: str, model: str, voice: str, text: str) -> Path:
        key = hashlib.sha256(
            f"{provider}|{model}|{voice}|{text}".encode()
        ).hexdigest()[:24]
        return self.root / provider / model / voice / f"{key}.mp3"

    def get(self, *, provider: str, model: str, voice: str, text: str) -> bytes | None:
        p = self._path(provider=provider, model=model, voice=voice, text=text)
        if p.exists():
            return p.read_bytes()
        return None

    def put(
        self, *, provider: str, model: str, voice: str, text: str, audio_bytes: bytes,
    ) -> None:
        p = self._path(provider=provider, model=model, voice=voice, text=text)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(audio_bytes)


def default_cache_dir() -> Path:
    """XDG-compliant default cache directory."""
    import os
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "gencast" / "tts"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/unit/test_tts_cache.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/tts/cache.py tests/unit/test_tts_cache.py
git commit -m "Plan B Task 9: TTSDiskCache (sha256 keyed, XDG layout)"
```

---

### Task B10: Audio stage — sentence split, concurrent TTS, concat with timing

**Files:**
- Create: `gencast/pipeline/audio.py`
- Test: `tests/component/test_audio_stage.py`

This is the first task that produces audio. Plan B Task 10 deliberately ships **without spatial FX** so we can validate the loop, caching, timing, and cost integration in isolation. Phase 4 (Tasks 11-15) plugs `audio_fx/` in.

Per turn:
1. `split_sentences(turn.text)` → list of sentences.
2. For each sentence: lookup in TTSDiskCache; on miss, call backend.synthesize; cache the bytes.
3. Each sentence becomes one `AudioClip(start_ms, end_ms, speaker_index, sentence_text, segment_index, audio: AudioSegment)`.
4. Sentences within a turn join with no gap. Turns join with 300 ms silence (`INTER_TURN_PAUSE_MS`).
5. After concat: peak normalize to `room.target_dbfs`.

Concurrency: 5 concurrent TTS calls via `asyncio.Semaphore`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_audio_stage.py
"""Audio stage end-to-end with stub backend."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gencast.pipeline.audio import (
    AudioClip,
    INTER_TURN_PAUSE_MS,
    run_audio_stage,
)
from gencast.pipeline.transcript import Transcript, TranscriptTurn


class StubBackend:
    """Returns 200ms of silence per call. Records calls."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    @property
    def backend_name(self) -> str:
        return "stub"

    @property
    def model(self) -> str:
        return "stub-1"

    @property
    def usd_per_audio_second(self) -> float:
        return 0.001

    async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
        self.calls.append((voice, text))
        from pydub import AudioSegment
        seg = AudioSegment.silent(duration=200, frame_rate=24000).set_channels(1)
        import io
        buf = io.BytesIO()
        seg.export(buf, format="mp3", bitrate="64k")
        return buf.getvalue(), 0.2


def _make_state(transcript_turns):
    """Minimal state factory for the audio stage."""
    from gencast.pipeline.transcript import Transcript
    state = MagicMock()
    state.transcript = Transcript(turns=transcript_turns)

    # Provide only what audio stage needs
    state.resolved.speaker.speakers = [
        MagicMock(name="Sophie", voice_id="nova"),
        MagicMock(name="Ben", voice_id="echo"),
    ]
    # MagicMock auto-name conflicts; explicitly set name attribute:
    state.resolved.speaker.speakers[0].name = "Sophie"
    state.resolved.speaker.speakers[1].name = "Ben"
    state.resolved.speaker.tts_provider = "stub"
    state.resolved.speaker.tts_model = "stub-1"

    state.resolved.room.target_dbfs = -1.0
    state.resolved.room.arc_deg = 120.0
    state.resolved.room.itd_max_ms = 0.6
    state.resolved.room.jitter_deg = 0.0
    state.resolved.room.reverb_wet = 0.0  # disable FX in this test
    state.resolved.room.ambience_db = None
    state.resolved.room.predelay_ms = 20.0
    state.resolved.room.reverb_t60_s = 0.30
    state.resolved.room.reverb_lpf_hz = 2000.0
    state.resolved.room.reverb_damping = 0.55
    state.resolved.room.table_radius_m = 0.85
    state.resolved.room.ambience_lpf_hz = 1500.0
    state.resolved.room.ambience_fan_rumble_db = 4.0

    state.cost = MagicMock()
    state.clips = []
    state.combined_audio = None
    return state


def test_audio_stage_one_turn_per_sentence(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hello there. How are you?", segment_index=0),
        TranscriptTurn(speaker="Ben", text="I'm well.", segment_index=0),
    ])
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))

    # 3 sentences total → 3 clips, 3 backend calls
    assert len(backend.calls) == 3
    assert len(state.clips) == 3
    # Voice routing: speaker name -> voice_id
    assert backend.calls[0] == ("nova", "Hello there.")
    assert backend.calls[1] == ("nova", "How are you?")
    assert backend.calls[2] == ("echo", "I'm well.")


def test_audio_stage_inter_turn_pause(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hi.", segment_index=0),
        TranscriptTurn(speaker="Ben", text="Bye.", segment_index=0),
    ])
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))

    # Two clips at 200ms each + one inter-turn pause
    assert state.clips[0].start_ms == 0
    assert state.clips[0].end_ms == 200
    assert state.clips[1].start_ms == 200 + INTER_TURN_PAUSE_MS
    assert state.clips[1].end_ms == 200 + INTER_TURN_PAUSE_MS + 200


def test_audio_stage_caches_misses(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Same text.", segment_index=0),
        TranscriptTurn(speaker="Sophie", text="Same text.", segment_index=0),
    ])
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))
    # Second call hits the cache
    assert len(backend.calls) == 1


def test_audio_stage_records_cost(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="One.", segment_index=0),
        TranscriptTurn(speaker="Ben", text="Two.", segment_index=0),
    ])
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))
    state.cost.record_tts.assert_called()
    # Total seconds across all calls = 2 × 0.2 = 0.4
    total_seconds = sum(
        c.kwargs["audio_seconds"] for c in state.cost.record_tts.call_args_list
    )
    assert abs(total_seconds - 0.4) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/component/test_audio_stage.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `gencast/pipeline/audio.py`**

```python
"""Audio stage — TTS dispatch, sentence-level clips, concat with timing.

Plan B Task 10 ships without spatial FX. Plan B Task 15 wires audio_fx/ in.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydub import AudioSegment

from gencast.tts import TTSBackend, get_backend, split_sentences
from gencast.tts.cache import TTSDiskCache, default_cache_dir

if TYPE_CHECKING:
    from gencast.pipeline import PodcastState

INTER_TURN_PAUSE_MS = 300


@dataclass
class AudioClip:
    """One sentence of TTS output, positioned in the final timeline."""
    start_ms: int
    end_ms: int
    speaker_index: int
    speaker_name: str
    sentence_text: str
    segment_index: int
    audio: AudioSegment


async def _synthesize_one(
    *, backend: TTSBackend, voice: str, text: str, cache: TTSDiskCache,
    semaphore: asyncio.Semaphore,
) -> tuple[AudioSegment, float, bool]:
    """Returns (audio_seg, audio_seconds, was_cache_hit)."""
    cached = cache.get(
        provider=backend.backend_name, model=backend.model, voice=voice, text=text,
    )
    if cached is not None:
        seg = AudioSegment.from_file(io.BytesIO(cached), format="mp3")
        return seg, len(seg) / 1000.0, True

    async with semaphore:
        audio_bytes, seconds = await backend.synthesize(voice=voice, text=text)
    cache.put(
        provider=backend.backend_name, model=backend.model, voice=voice, text=text,
        audio_bytes=audio_bytes,
    )
    seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    return seg, seconds, False


async def run_audio_stage(
    state: "PodcastState",
    *,
    backend: TTSBackend | None = None,
    cache_dir: Path | None = None,
    concurrency: int = 5,
) -> None:
    """Populate state.clips and state.combined_audio. No spatial FX in Plan B Task 10."""
    assert state.transcript is not None, "transcript must be populated"
    sp = state.resolved.speaker
    if backend is None:
        backend = get_backend(sp.tts_provider, sp.tts_model, **(sp.tts_config or {}))
    cache = TTSDiskCache(cache_dir or default_cache_dir())

    # Map speaker name -> (index, voice)
    speaker_lookup = {s.name: (i, s.voice_id) for i, s in enumerate(sp.speakers)}

    # Build the synthesis job list (one per sentence)
    jobs: list[tuple[int, int, str, str, int, str, str]] = []
    # tuple = (turn_index, sentence_index_within_turn, speaker_name, sentence_text, segment_index, voice, _)
    for turn_index, turn in enumerate(state.transcript.turns):
        if turn.speaker not in speaker_lookup:
            raise ValueError(
                f"Turn {turn_index}: unknown speaker {turn.speaker!r}; "
                f"valid: {list(speaker_lookup)}"
            )
        spk_idx, voice = speaker_lookup[turn.speaker]
        seg_idx = turn.segment_index if turn.segment_index is not None else 0
        for s_idx, sentence in enumerate(split_sentences(turn.text)):
            jobs.append((turn_index, s_idx, turn.speaker, sentence, seg_idx, voice, ""))

    # Synthesize concurrently
    semaphore = asyncio.Semaphore(concurrency)

    async def _do(j):
        _, _, _, sentence, _, voice, _ = j
        return await _synthesize_one(
            backend=backend, voice=voice, text=sentence,
            cache=cache, semaphore=semaphore,
        )

    results = await asyncio.gather(*(_do(j) for j in jobs))

    # Stitch clips with timing + record cost for non-cached
    clips: list[AudioClip] = []
    cursor_ms = 0
    last_turn_index = -1
    combined = AudioSegment.empty()

    for j, (audio, seconds, hit) in zip(jobs, results):
        turn_index, s_idx, speaker_name, sentence_text, seg_idx, voice, _ = j
        spk_idx = speaker_lookup[speaker_name][0]

        if last_turn_index != -1 and turn_index != last_turn_index:
            cursor_ms += INTER_TURN_PAUSE_MS
            combined += AudioSegment.silent(
                duration=INTER_TURN_PAUSE_MS, frame_rate=audio.frame_rate
            ).set_channels(audio.channels)

        start = cursor_ms
        end = cursor_ms + len(audio)
        clips.append(AudioClip(
            start_ms=start, end_ms=end,
            speaker_index=spk_idx, speaker_name=speaker_name,
            sentence_text=sentence_text, segment_index=seg_idx,
            audio=audio,
        ))
        combined += audio
        cursor_ms = end
        last_turn_index = turn_index

        if not hit:
            usd = seconds * backend.usd_per_audio_second
            state.cost.record_tts(
                "tts",
                backend=backend.backend_name,
                model=backend.model,
                audio_seconds=seconds,
                usd=usd,
            )

    state.clips = clips
    state.combined_audio = combined
```

- [ ] **Step 4: Extend `PodcastState` for clips + combined_audio**

Modify `gencast/pipeline/__init__.py` (add fields to `PodcastState`):

```python
# (top of file imports)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pydub import AudioSegment
    from gencast.pipeline.audio import AudioClip


@dataclass
class PodcastState:
    notebook: Notebook
    resolved: ResolvedNotebook
    source_text: str = ""
    source_tokens_original: int = 0
    source_tokens_final: int = 0
    outline: Outline | None = None
    transcript: Transcript | None = None
    clips: list["AudioClip"] = field(default_factory=list)
    combined_audio: "AudioSegment | None" = None
    cost: CostMeter = field(default_factory=CostMeter)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/component/test_audio_stage.py -v`
Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add gencast/pipeline/audio.py gencast/pipeline/__init__.py tests/component/test_audio_stage.py
git commit -m "Plan B Task 10: run_audio_stage — sentence split, concurrent TTS, clip timing"
```

---

## Phase 4 — audio_fx + room profile

The next four tasks (B11–B14) lift code verbatim from the `scratch/` harnesses (on `main`), with two adaptations: the helpers move under `gencast/audio_fx/` and the SciPy LPF stays as a soft dependency (already in requirements via `pydub`'s ecosystem; explicit on first import).

The locked v1 chain (from `scratch/final_harness.py:V1_DEFAULT`):

```
mono → pan + ITD → SchroederReverb(t60, wet, lpf, damping) → predelay 20ms
     → inverse-square distance → ambience bed (NC 20) → ±jitter_deg → peak normalize
```

All parameters drive from `RoomProfile` (already shipped in Plan A).

### Task B11: `audio_fx/pan_itd.py` + `_npbridge.py`

**Files:**
- Create: `gencast/audio_fx/__init__.py` (empty marker for now; orchestrator added in B15)
- Create: `gencast/audio_fx/_npbridge.py`
- Create: `gencast/audio_fx/pan_itd.py`
- Test: `tests/unit/test_audio_fx_pan_itd.py`

`_npbridge.py` contains `seg_to_np` / `np_to_seg`, the AudioSegment ↔ ndarray conversion lifted from `scratch/spatial_test.py:197-225`. Re-used by every audio_fx module.

Source: `scratch/no_hrtf_test.py:62-96` (`pan_position`, `render_pan_itd`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_audio_fx_pan_itd.py
"""Pan + ITD — pan position math + stereo output shape."""

from __future__ import annotations

from pydub import AudioSegment

from gencast.audio_fx.pan_itd import pan_position, render_pan_itd


def test_pan_position_caps_at_pm_one():
    assert pan_position(0) == 0.0
    assert pan_position(90) == 1.0
    assert pan_position(-90) == -1.0
    assert pan_position(180) == 1.0
    assert pan_position(-180) == -1.0


def test_render_pan_itd_returns_stereo():
    mono = AudioSegment.silent(duration=200, frame_rate=44100).set_channels(1)
    stereo = render_pan_itd(mono, azimuth_deg=45.0, use_itd=True)
    assert stereo.channels == 2


def test_render_pan_itd_no_itd_when_centered():
    mono = AudioSegment.silent(duration=200, frame_rate=44100).set_channels(1)
    stereo = render_pan_itd(mono, azimuth_deg=0.0, use_itd=True)
    assert stereo.channels == 2
    # Length unchanged when centered (no silence padding inserted)
    assert len(stereo) == 200


def test_render_pan_itd_left_source_delays_right_ear():
    mono = AudioSegment.silent(duration=200, frame_rate=44100).set_channels(1)
    stereo = render_pan_itd(mono, azimuth_deg=-90.0, use_itd=True, itd_max_ms=0.6)
    # Length grew slightly due to silence-padding for ITD
    assert len(stereo) >= 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/unit/test_audio_fx_pan_itd.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `_npbridge.py`**

```python
"""AudioSegment <-> numpy bridge. Lifted from scratch/spatial_test.py:197-225."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment


def seg_to_np(seg: AudioSegment) -> np.ndarray:
    """AudioSegment -> float32 ndarray of shape (channels, samples), range [-1, 1]."""
    samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
    if seg.channels == 2:
        samples = samples.reshape(-1, 2).T  # (2, N)
    else:
        samples = samples.reshape(1, -1)
    samples = samples / float(2 ** (8 * seg.sample_width - 1))
    return samples


def np_to_seg(arr: np.ndarray, sample_rate: int) -> AudioSegment:
    """float32 (channels, samples) ndarray -> stereo AudioSegment."""
    if arr.ndim == 1:
        arr = np.stack([arr, arr])
    arr = np.clip(arr, -1.0, 1.0)
    arr = (arr * 32767.0).astype(np.int16)
    interleaved = arr.T.flatten().tobytes()
    return AudioSegment(
        data=interleaved,
        sample_width=2,
        frame_rate=sample_rate,
        channels=2,
    )
```

- [ ] **Step 4: Implement `pan_itd.py`**

```python
"""Amplitude pan + ITD. Lifted from scratch/no_hrtf_test.py:62-96."""

from __future__ import annotations

from pydub import AudioSegment


def pan_position(azimuth_deg: float) -> float:
    """Map azimuth (deg) to pydub-style pan position. ±90° → ±1.0, capped."""
    return max(-1.0, min(1.0, azimuth_deg / 90.0))


def render_pan_itd(
    mono: AudioSegment,
    azimuth_deg: float,
    *,
    use_itd: bool = True,
    itd_max_ms: float = 0.6,
) -> AudioSegment:
    """Convert mono → stereo with amplitude pan + (optional) ITD."""
    pos = pan_position(azimuth_deg)
    seg = mono.set_channels(2) if mono.channels < 2 else mono
    seg = seg.pan(pos)
    if not use_itd:
        return seg
    itd_ms = abs(pos) * itd_max_ms
    if itd_ms < 0.01:
        return seg
    silence = AudioSegment.silent(duration=int(itd_ms), frame_rate=seg.frame_rate)
    channels = seg.split_to_mono()
    if len(channels) != 2:
        return seg
    left, right = channels
    if pos < 0:  # left source: delay right ear
        right = silence + right
        left = left + silence
    else:
        left = silence + left
        right = right + silence
    return AudioSegment.from_mono_audiosegments(left, right)
```

- [ ] **Step 5: Add the empty audio_fx package marker**

```python
# gencast/audio_fx/__init__.py
"""Audio FX package — orchestrator added in Plan B Task 15."""
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/unit/test_audio_fx_pan_itd.py -v`
Expected: 4 tests pass.

- [ ] **Step 7: Commit**

```bash
git add gencast/audio_fx/__init__.py gencast/audio_fx/_npbridge.py gencast/audio_fx/pan_itd.py tests/unit/test_audio_fx_pan_itd.py
git commit -m "Plan B Task 11: audio_fx/pan_itd + numpy bridge (lifted from scratch)"
```

---

### Task B12: `audio_fx/reverb.py` (SchroederReverb)

**Files:**
- Create: `gencast/audio_fx/reverb.py`
- Test: `tests/unit/test_audio_fx_reverb.py`

Lifted verbatim from `scratch/spatial_test.py:421-545`. Replace the local `seg_to_np`/`np_to_seg` import with `from gencast.audio_fx._npbridge import ...`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_audio_fx_reverb.py
"""SchroederReverb — wet/dry mix, output stereo, finite samples."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx.reverb import SchroederReverb


def test_reverb_returns_stereo():
    sr = 44100
    seg = AudioSegment.silent(duration=200, frame_rate=sr).set_channels(2)
    rv = SchroederReverb(sample_rate=sr, t60_s=0.30)
    out = rv.apply(seg, wet=0.05)
    assert out.channels == 2


def test_reverb_dry_when_wet_zero():
    """wet=0 should approximate the input (allowing for the all-pass chain)."""
    sr = 44100
    rng = np.random.default_rng(0)
    n = sr // 4
    raw = (rng.normal(0, 0.1, n) * 32767).astype(np.int16)
    seg = AudioSegment(
        raw.tobytes(), sample_width=2, frame_rate=sr, channels=1,
    )
    rv = SchroederReverb(sample_rate=sr, t60_s=0.30)
    out = rv.apply(seg, wet=0.0)
    assert len(out) == len(seg)


def test_reverb_t60_attribute_recorded():
    rv = SchroederReverb(sample_rate=44100, t60_s=0.50)
    assert abs(rv.t60_s - 0.50) < 1e-6
    assert all(0 < g < 1 for g in rv.comb_feedback)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/unit/test_audio_fx_reverb.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `reverb.py` (verbatim lift)**

Copy `scratch/spatial_test.py:421-545` (the `SchroederReverb` class) into `gencast/audio_fx/reverb.py`. Adjust imports:

```python
"""Tiny Schroeder reverb. Lifted from scratch/spatial_test.py:421-545.

4 parallel feedback comb filters → 2 series allpass filters. Feedback gain per
delay so all combs decay to the same T60.
"""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np


class SchroederReverb:
    DEFAULT_COMB_DELAYS_MS = (29.7, 37.1, 41.1, 43.7)
    ALLPASS_DELAYS_MS = (5.0, 1.7)
    ALLPASS_GAIN = 0.5
    DEFAULT_WET = 0.05
    DEFAULT_T60_S = 0.25

    def __init__(
        self,
        sample_rate: int = 44100,
        comb_delays_ms: tuple[float, ...] = DEFAULT_COMB_DELAYS_MS,
        t60_s: float = DEFAULT_T60_S,
    ):
        self.sr = sample_rate
        self.t60_s = t60_s
        self.comb_delays_ms = comb_delays_ms
        self.comb_delays = [int(d * sample_rate / 1000.0) for d in comb_delays_ms]
        self.allpass_delays = [int(d * sample_rate / 1000.0) for d in self.ALLPASS_DELAYS_MS]
        self.comb_feedback = tuple(
            10 ** (-3 * (d_ms / 1000.0) / t60_s) for d_ms in comb_delays_ms
        )

    @staticmethod
    def _comb(signal: np.ndarray, delay: int, feedback: float, damping: float = 0.0) -> np.ndarray:
        out = np.zeros_like(signal)
        buf = np.zeros(delay, dtype=np.float32)
        idx = 0
        lpf_state = np.float32(0.0)
        a = np.float32(max(0.0, min(0.95, damping)))
        if a == 0.0:
            for i in range(len(signal)):
                delayed = buf[idx]
                buf[idx] = signal[i] + feedback * delayed
                out[i] = delayed
                idx = (idx + 1) % delay
        else:
            for i in range(len(signal)):
                delayed = buf[idx]
                lpf_state = a * lpf_state + (1.0 - a) * delayed
                buf[idx] = signal[i] + feedback * lpf_state
                out[i] = delayed
                idx = (idx + 1) % delay
        return out

    @staticmethod
    def _allpass(signal: np.ndarray, delay: int, gain: float) -> np.ndarray:
        out = np.zeros_like(signal)
        buf = np.zeros(delay, dtype=np.float32)
        idx = 0
        for i in range(len(signal)):
            delayed = buf[idx]
            new = signal[i] + gain * delayed
            buf[idx] = new
            out[i] = -gain * new + delayed
            idx = (idx + 1) % delay
        return out

    def apply(
        self,
        seg: AudioSegment,
        wet: float = DEFAULT_WET,
        wet_lpf_hz: float | None = None,
        damping: float = 0.0,
    ) -> AudioSegment:
        if seg.frame_rate != self.sr:
            seg = seg.set_frame_rate(self.sr)
        signal = seg_to_np(seg)
        if signal.shape[0] == 1:
            signal = np.tile(signal, (2, 1))

        out = np.zeros_like(signal)
        for ch in (0, 1):
            x = signal[ch]
            comb_sum = np.zeros_like(x)
            for d, fb in zip(self.comb_delays, self.comb_feedback):
                comb_sum += self._comb(x, d, fb, damping=damping)
            comb_sum /= len(self.comb_delays)
            y = comb_sum
            for d in self.allpass_delays:
                y = self._allpass(y, d, self.ALLPASS_GAIN)
            out[ch] = y

        if wet_lpf_hz is not None:
            from scipy.signal import iirfilter, sosfilt
            sos = iirfilter(2, wet_lpf_hz, btype="low", ftype="butter",
                            fs=self.sr, output="sos")
            for ch in range(out.shape[0]):
                out[ch] = sosfilt(sos, out[ch])

        mixed = (1.0 - wet) * signal + wet * out
        peak = np.max(np.abs(mixed))
        if peak > 0.99:
            mixed *= 0.99 / peak

        return np_to_seg(mixed, sample_rate=self.sr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/unit/test_audio_fx_reverb.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/audio_fx/reverb.py tests/unit/test_audio_fx_reverb.py
git commit -m "Plan B Task 12: audio_fx/reverb — SchroederReverb (lifted)"
```

---

### Task B13: `audio_fx/distance.py` + `audio_fx/normalize.py`

**Files:**
- Create: `gencast/audio_fx/distance.py`
- Create: `gencast/audio_fx/normalize.py`
- Test: `tests/unit/test_audio_fx_distance.py`
- Test: `tests/unit/test_audio_fx_normalize.py`

`distance` — lifted from `scratch/immersion_test.py:185-198` (`attenuate_for_distance`). `normalize` — lifted from `scratch/spatial_test.py:551-561` (`normalize_peak`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_audio_fx_distance.py
import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.distance import attenuate_for_distance


def _random_seg(sr=44100, n=4410):
    rng = np.random.default_rng(0)
    arr = rng.normal(0, 0.3, (2, n)).astype(np.float32)
    return np_to_seg(arr, sr)


def test_no_change_at_reference_distance():
    seg = _random_seg()
    out = attenuate_for_distance(seg, distance_m=0.85, ref_distance_m=0.85)
    pre, post = seg_to_np(seg), seg_to_np(out)
    assert np.allclose(pre, post, atol=1e-3)


def test_attenuates_at_double_distance():
    seg = _random_seg()
    out = attenuate_for_distance(seg, distance_m=1.70, ref_distance_m=0.85)
    pre_peak = np.max(np.abs(seg_to_np(seg)))
    post_peak = np.max(np.abs(seg_to_np(out)))
    # -6 dB ≈ ×0.5
    assert 0.4 < (post_peak / pre_peak) < 0.6
```

```python
# tests/unit/test_audio_fx_normalize.py
import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.normalize import peak_normalize


def test_peak_normalize_to_minus_one_dbfs():
    sr = 44100
    rng = np.random.default_rng(1)
    arr = rng.normal(0, 0.05, (2, sr // 4)).astype(np.float32)  # very low peak
    seg = np_to_seg(arr, sr)
    out = peak_normalize(seg, target_dbfs=-1.0)
    out_peak = np.max(np.abs(seg_to_np(out)))
    target = 10 ** (-1.0 / 20.0)
    assert abs(out_peak - target) < 0.02
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/unit/test_audio_fx_distance.py tests/unit/test_audio_fx_normalize.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `distance.py`**

```python
"""Inverse-square distance attenuation. Lifted from scratch/immersion_test.py:185-198."""

from __future__ import annotations

import math

from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np


def attenuate_for_distance(
    seg: AudioSegment, distance_m: float, ref_distance_m: float = 0.85,
) -> AudioSegment:
    """-6 dB per doubling of distance, relative to reference radius."""
    if distance_m <= 0 or ref_distance_m <= 0:
        return seg
    db = 20.0 * math.log10(ref_distance_m / distance_m)
    if abs(db) < 0.01:
        return seg
    arr = seg_to_np(seg)
    arr = arr * (10 ** (db / 20.0))
    return np_to_seg(arr, sample_rate=seg.frame_rate)
```

- [ ] **Step 4: Implement `normalize.py`**

```python
"""Peak normalize. Lifted from scratch/spatial_test.py:551-561."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np


def peak_normalize(seg: AudioSegment, target_dbfs: float = -1.0) -> AudioSegment:
    """Scale so the absolute peak hits target_dbfs (dBFS, ≤ 0)."""
    arr = seg_to_np(seg)
    peak = float(np.max(np.abs(arr)))
    if peak < 1e-6:
        return seg
    target_linear = 10 ** (target_dbfs / 20.0)
    arr = arr * (target_linear / peak)
    return np_to_seg(arr, sample_rate=seg.frame_rate)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/unit/test_audio_fx_distance.py tests/unit/test_audio_fx_normalize.py -v`
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add gencast/audio_fx/distance.py gencast/audio_fx/normalize.py tests/unit/test_audio_fx_distance.py tests/unit/test_audio_fx_normalize.py
git commit -m "Plan B Task 13: audio_fx/distance + normalize (lifted)"
```

---

### Task B14: `audio_fx/ambience.py`

**Files:**
- Create: `gencast/audio_fx/ambience.py`
- Test: `tests/unit/test_audio_fx_ambience.py`

Lifted from `scratch/immersion_test.py:249-318`. Generates a colored-noise NC 20 bed (pink + LPF + optional fan rumble) and mixes it under a foreground.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_audio_fx_ambience.py
"""Ambience bed shape + mix correctness."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.ambience import make_ambience_bed, mix_ambience


def test_ambience_bed_length_matches():
    sr = 44100
    bed = make_ambience_bed(duration_ms=500, sample_rate=sr, level_db=-60.0)
    assert abs(len(bed) - 500) < 5
    assert bed.channels == 2


def test_ambience_bed_level_below_target():
    sr = 44100
    bed = make_ambience_bed(duration_ms=500, sample_rate=sr, level_db=-50.0)
    arr = seg_to_np(bed)
    peak = np.max(np.abs(arr))
    target = 10 ** (-50.0 / 20.0)
    assert peak <= target + 1e-3


def test_mix_ambience_preserves_foreground_peak_roughly():
    sr = 44100
    rng = np.random.default_rng(2)
    fg_arr = rng.normal(0, 0.2, (2, sr // 4)).astype(np.float32)
    fg = np_to_seg(fg_arr, sr)
    bed = make_ambience_bed(duration_ms=len(fg), sample_rate=sr, level_db=-70.0)
    out = mix_ambience(fg, bed)
    out_arr = seg_to_np(out)
    assert out_arr.shape == fg_arr.shape
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/unit/test_audio_fx_ambience.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `ambience.py` (verbatim lift)**

```python
"""Ambience bed (NC 20 colored noise) + mix. Lifted from scratch/immersion_test.py:249-318."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np


def make_ambience_bed(
    duration_ms: int,
    sample_rate: int = 44100,
    level_db: float = -50.0,
    lpf_hz: float = 1500.0,
    fan_rumble_db: float = 4.0,
) -> AudioSegment:
    """Pink-noise base + LPF + optional 80Hz low-shelf for fan rumble. Stereo."""
    from scipy.signal import iirfilter, sosfilt

    n_samples = int(round(duration_ms * 0.001 * sample_rate))
    rng = np.random.default_rng(42)
    white = rng.normal(0.0, 1.0, n_samples).astype(np.float32)
    n_fft = 1
    while n_fft < n_samples:
        n_fft *= 2
    spectrum = np.fft.rfft(white, n=n_fft)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    shaping = np.where(freqs > 0, 1.0 / np.sqrt(freqs + 10.0), 1.0)
    shaping /= shaping.max()
    pink = np.fft.irfft(spectrum * shaping, n=n_fft)[:n_samples].astype(np.float32)

    sos = iirfilter(2, lpf_hz, btype="low", ftype="butter", fs=sample_rate, output="sos")
    pink = sosfilt(sos, pink).astype(np.float32)

    if fan_rumble_db > 0.0:
        shelf = iirfilter(2, 80, btype="low", ftype="butter", fs=sample_rate, output="sos")
        rumble = sosfilt(shelf, pink).astype(np.float32)
        boost = (10 ** (fan_rumble_db / 20.0)) - 1.0
        pink = (pink + boost * rumble).astype(np.float32)

    decorr_samples = int(round(0.0005 * sample_rate))
    pink_l = pink
    pink_r = np.concatenate([np.zeros(decorr_samples, dtype=np.float32), pink])[: len(pink_l)]
    stereo = np.stack([pink_l, pink_r])
    target_amp = 10 ** (level_db / 20.0)
    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo * (target_amp / peak)
    return np_to_seg(stereo, sample_rate=sample_rate)


def mix_ambience(foreground: AudioSegment, ambience: AudioSegment) -> AudioSegment:
    """Sum ambience under foreground, matching length."""
    f_arr = seg_to_np(foreground)
    a_arr = seg_to_np(ambience)
    n = f_arr.shape[1]
    if a_arr.shape[1] < n:
        reps = (n // a_arr.shape[1]) + 1
        a_arr = np.tile(a_arr, (1, reps))
    a_arr = a_arr[:, :n]
    out = f_arr + a_arr
    peak = np.max(np.abs(out))
    if peak > 0.99:
        out *= 0.99 / peak
    return np_to_seg(out, sample_rate=foreground.frame_rate)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/unit/test_audio_fx_ambience.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/audio_fx/ambience.py tests/unit/test_audio_fx_ambience.py
git commit -m "Plan B Task 14: audio_fx/ambience — pink-noise NC 20 bed (lifted)"
```

---

### Task B15: `apply_room` orchestrator + integrate into audio stage

**Files:**
- Modify: `gencast/audio_fx/__init__.py` (add the orchestrator)
- Modify: `gencast/pipeline/audio.py` (apply per-clip + ambience)
- Test: `tests/component/test_audio_fx.py`

Per-speaker azimuth: `front_arc_azimuths(num_speakers, arc_deg)` — outer speakers at ±arc/2, inner speakers evenly spaced (mirrors `scratch/spatial_test.py:112`). Plus optional ±jitter_deg per sentence.

Per-clip pipeline (matches `scratch/final_harness.py:render_dialogue`):

```
mono_set_channels(1) → render_pan_itd → SchroederReverb.apply → predelay swap
                    → attenuate_for_distance(speaker_seat_distance)
```

Stage-level (after concat):

```
combined → mix_ambience(make_ambience_bed) → peak_normalize(target_dbfs)
```

A persistent `SchroederReverb` instance is created once per stage (initialised from `room.reverb_t60_s`).

- [ ] **Step 1: Add `front_arc_azimuths` helper to `audio_fx/__init__.py`**

```python
"""Audio FX orchestrator — applies a RoomProfile to clips and the combined mix."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.ambience import make_ambience_bed, mix_ambience
from gencast.audio_fx.distance import attenuate_for_distance
from gencast.audio_fx.normalize import peak_normalize
from gencast.audio_fx.pan_itd import render_pan_itd
from gencast.audio_fx.reverb import SchroederReverb

if TYPE_CHECKING:
    from gencast.profiles.schemas import RoomProfile


# Listener at room centre. Mirrors scratch/immersion_test.py.
_LISTENER_POS = (0.0, 0.0, 1.2)


def front_arc_azimuths(n_speakers: int, arc_deg: float = 120.0) -> list[float]:
    """Spread n speakers across a front arc; outer speakers at ±arc/2.

    n=1 → [0]
    n=2 → [-arc/2, +arc/2]
    n=3+ → outer at ±arc/2, evenly spaced inside.
    """
    if n_speakers <= 0:
        return []
    if n_speakers == 1:
        return [0.0]
    if n_speakers == 2:
        return [-arc_deg / 2, arc_deg / 2]
    step = arc_deg / (n_speakers - 1)
    return [-arc_deg / 2 + i * step for i in range(n_speakers)]


def speaker_seat_distance(
    azimuth_deg: float, table_radius_m: float,
) -> float:
    """Distance from listener to the seat at this azimuth on the round table."""
    sx = _LISTENER_POS[0] + table_radius_m * math.sin(math.radians(azimuth_deg))
    sy = _LISTENER_POS[1] + table_radius_m * math.cos(math.radians(azimuth_deg))
    sz = 1.2  # speaker mouth height
    return math.sqrt(
        (sx - _LISTENER_POS[0]) ** 2
        + (sy - _LISTENER_POS[1]) ** 2
        + (sz - _LISTENER_POS[2]) ** 2
    )


def _apply_predelay(
    direct: AudioSegment, mixed: AudioSegment, predelay_ms: float, target_sr: int,
) -> AudioSegment:
    """Replace the first `predelay_ms` of `mixed` with the dry signal."""
    if predelay_ms <= 0:
        return mixed
    pre_n = int(round(predelay_ms * 0.001 * target_sr))
    if pre_n <= 0:
        return mixed
    mixed_arr = seg_to_np(mixed)
    direct_arr = seg_to_np(direct)
    if mixed_arr.shape[1] < pre_n or direct_arr.shape[1] < pre_n:
        return mixed
    blended = mixed_arr.copy()
    blended[:, :pre_n] = direct_arr[:, :pre_n]
    return np_to_seg(blended, sample_rate=target_sr)


def render_clip_with_room(
    mono: AudioSegment,
    *,
    azimuth_deg: float,
    distance_m: float,
    room: "RoomProfile",
    reverb: SchroederReverb,
    target_sr: int,
) -> AudioSegment:
    """Apply the per-clip locked v1 pipeline to one sentence."""
    if mono.frame_rate != target_sr:
        mono = mono.set_frame_rate(target_sr)
    if mono.channels != 1:
        mono = mono.set_channels(1)

    direct = render_pan_itd(mono, azimuth_deg, use_itd=True, itd_max_ms=room.itd_max_ms)

    if room.reverb_wet > 0.0:
        wet = reverb.apply(
            direct,
            wet=room.reverb_wet,
            wet_lpf_hz=room.reverb_lpf_hz,
            damping=room.reverb_damping,
        )
        seg = _apply_predelay(direct, wet, room.predelay_ms, target_sr)
    else:
        seg = direct

    seg = attenuate_for_distance(seg, distance_m, ref_distance_m=room.table_radius_m)
    return seg
```

- [ ] **Step 2: Modify `gencast/pipeline/audio.py` to apply room FX**

Replace the body of `run_audio_stage` so each clip goes through `render_clip_with_room` and the combined mix gets ambience + normalize. Diff:

```python
# (top of file — add imports)
import numpy as np
from gencast.audio_fx import (
    front_arc_azimuths,
    render_clip_with_room,
    speaker_seat_distance,
)
from gencast.audio_fx.ambience import make_ambience_bed, mix_ambience
from gencast.audio_fx.normalize import peak_normalize
from gencast.audio_fx.reverb import SchroederReverb

TARGET_SR = 44100
```

Replace the stitching section of `run_audio_stage` (after the `results = await asyncio.gather(...)` line) with:

```python
    # Per-speaker azimuth + jitter
    n_speakers = len(sp.speakers)
    azimuths = front_arc_azimuths(n_speakers, state.resolved.room.arc_deg)
    rng = np.random.default_rng(2026)
    reverb = SchroederReverb(sample_rate=TARGET_SR, t60_s=state.resolved.room.reverb_t60_s)

    clips: list[AudioClip] = []
    cursor_ms = 0
    last_turn_index = -1
    combined = AudioSegment.empty()

    for j, (raw_audio, seconds, hit) in zip(jobs, results):
        turn_index, s_idx, speaker_name, sentence_text, seg_idx, voice, _ = j
        spk_idx = speaker_lookup[speaker_name][0]

        # Per-sentence azimuth jitter
        base_az = azimuths[spk_idx]
        jit = (
            (rng.random() * 2.0 - 1.0) * state.resolved.room.jitter_deg
            if state.resolved.room.jitter_deg
            else 0.0
        )
        az = base_az + jit
        dist = speaker_seat_distance(az, state.resolved.room.table_radius_m)

        # Apply per-clip room FX (mono → stereo with locked v1 chain)
        spatial = render_clip_with_room(
            raw_audio,
            azimuth_deg=az, distance_m=dist,
            room=state.resolved.room, reverb=reverb,
            target_sr=TARGET_SR,
        )

        if last_turn_index != -1 and turn_index != last_turn_index:
            cursor_ms += INTER_TURN_PAUSE_MS
            combined += AudioSegment.silent(
                duration=INTER_TURN_PAUSE_MS, frame_rate=TARGET_SR
            ).set_channels(2)

        start = cursor_ms
        end = cursor_ms + len(spatial)
        clips.append(AudioClip(
            start_ms=start, end_ms=end,
            speaker_index=spk_idx, speaker_name=speaker_name,
            sentence_text=sentence_text, segment_index=seg_idx,
            audio=spatial,
        ))
        combined += spatial
        cursor_ms = end
        last_turn_index = turn_index

        if not hit:
            usd = seconds * backend.usd_per_audio_second
            state.cost.record_tts(
                "tts", backend=backend.backend_name, model=backend.model,
                audio_seconds=seconds, usd=usd,
            )

    # Stage-level: ambience bed + peak normalize
    if state.resolved.room.ambience_db is not None:
        ambience = make_ambience_bed(
            duration_ms=len(combined),
            sample_rate=TARGET_SR,
            level_db=state.resolved.room.ambience_db,
            lpf_hz=state.resolved.room.ambience_lpf_hz,
            fan_rumble_db=state.resolved.room.ambience_fan_rumble_db,
        )
        combined = mix_ambience(combined, ambience)

    combined = peak_normalize(combined, target_dbfs=state.resolved.room.target_dbfs)

    state.clips = clips
    state.combined_audio = combined
```

- [ ] **Step 3: Write the failing component test**

```python
# tests/component/test_audio_fx.py
"""Audio FX integration in the audio stage. Reuses StubBackend from B10."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from gencast.pipeline.audio import run_audio_stage
from gencast.pipeline.transcript import TranscriptTurn

# Import the stub backend used in test_audio_stage
from tests.component.test_audio_stage import StubBackend, _make_state


def test_apply_room_produces_stereo_output(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hello.", segment_index=0),
        TranscriptTurn(speaker="Ben", text="Hi.", segment_index=0),
    ])
    # Re-enable FX (B10 test had wet=0). Apply moderate values.
    state.resolved.room.reverb_wet = 0.05
    state.resolved.room.ambience_db = -70.0

    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))

    assert state.combined_audio is not None
    assert state.combined_audio.channels == 2
    # All clips stereo too
    for c in state.clips:
        assert c.audio.channels == 2


def test_zero_wet_skips_reverb(tmp_path):
    """When reverb_wet=0, render_clip_with_room should still produce stereo."""
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hi.", segment_index=0),
    ])
    state.resolved.room.reverb_wet = 0.0
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))
    assert state.clips[0].audio.channels == 2


def test_ambience_disabled_when_db_none(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hi.", segment_index=0),
    ])
    state.resolved.room.reverb_wet = 0.0
    state.resolved.room.ambience_db = None
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))
    # Just check it ran without raising and produced output
    assert state.combined_audio is not None
```

- [ ] **Step 4: Run all audio tests to verify they pass**

Run: `./venv/bin/pytest tests/component/test_audio_stage.py tests/component/test_audio_fx.py tests/unit/test_audio_fx_*.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add gencast/audio_fx/__init__.py gencast/pipeline/audio.py tests/component/test_audio_fx.py
git commit -m "Plan B Task 15: apply_room orchestrator + audio_stage integration (locked v1 chain)"
```

---

## Phase 5 — Subtitles, M4A mux, CLI

### Task B16: Native SRT subtitles from clip timing

**Files:**
- Create: `gencast/pipeline/subtitles.py`
- Test: `tests/component/test_subtitles.py`

The audio stage already records every clip's `start_ms`/`end_ms`. SRT is built directly from `state.clips` — one entry per clip (per sentence). No Whisper post-pass needed for the default flow. (Whisper STT path remains for `gencast subtitle EXISTING.mp3`; that's Plan C.)

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_subtitles.py
"""SRT building from clip timing."""

from __future__ import annotations

from pydub import AudioSegment

from gencast.pipeline.audio import AudioClip
from gencast.pipeline.subtitles import SrtEntry, build_native_srt, srt_format


def _clip(start, end, speaker, text):
    seg = AudioSegment.silent(duration=end - start, frame_rate=44100).set_channels(2)
    return AudioClip(
        start_ms=start, end_ms=end,
        speaker_index=0, speaker_name=speaker,
        sentence_text=text, segment_index=0, audio=seg,
    )


def test_build_native_srt_one_entry_per_clip():
    clips = [
        _clip(0, 1500, "Sophie", "Hello there."),
        _clip(1500, 3500, "Ben", "How are you?"),
    ]
    entries = build_native_srt(clips, include_speaker=True)
    assert len(entries) == 2
    assert entries[0].start_ms == 0
    assert entries[0].end_ms == 1500
    assert entries[0].text == "[Sophie] Hello there."
    assert entries[1].text == "[Ben] How are you?"


def test_build_native_srt_no_speaker_label():
    clips = [_clip(0, 1500, "Sophie", "Hi.")]
    entries = build_native_srt(clips, include_speaker=False)
    assert entries[0].text == "Hi."


def test_srt_format_one_entry():
    e = SrtEntry(index=1, start_ms=0, end_ms=1234, text="Hello.")
    out = srt_format([e])
    expected = (
        "1\n"
        "00:00:00,000 --> 00:00:01,234\n"
        "Hello.\n"
        "\n"
    )
    assert out == expected


def test_srt_format_multiple_entries():
    es = [
        SrtEntry(index=1, start_ms=0, end_ms=1500, text="One."),
        SrtEntry(index=2, start_ms=1500, end_ms=3500, text="Two."),
    ]
    out = srt_format(es)
    assert "1\n00:00:00,000 --> 00:00:01,500\nOne." in out
    assert "2\n00:00:01,500 --> 00:00:03,500\nTwo." in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/component/test_subtitles.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `gencast/pipeline/subtitles.py`**

```python
"""Native SRT subtitles built from AudioClip timing — no Whisper required."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gencast.pipeline.audio import AudioClip


@dataclass
class SrtEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str


def build_native_srt(
    clips: list["AudioClip"], *, include_speaker: bool = True,
) -> list[SrtEntry]:
    """Map each clip to one SRT entry."""
    out: list[SrtEntry] = []
    for i, clip in enumerate(clips, start=1):
        text = (
            f"[{clip.speaker_name}] {clip.sentence_text}"
            if include_speaker
            else clip.sentence_text
        )
        out.append(SrtEntry(
            index=i, start_ms=clip.start_ms, end_ms=clip.end_ms, text=text,
        ))
    return out


def _format_ts(ms: int) -> str:
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def srt_format(entries: list[SrtEntry]) -> str:
    """Render a list of SrtEntry as a complete SRT file string."""
    parts: list[str] = []
    for e in entries:
        parts.append(
            f"{e.index}\n"
            f"{_format_ts(e.start_ms)} --> {_format_ts(e.end_ms)}\n"
            f"{e.text}\n"
        )
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/component/test_subtitles.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/subtitles.py tests/component/test_subtitles.py
git commit -m "Plan B Task 16: native SRT from AudioClip timing (no Whisper)"
```

---

### Task B17: Packaging — M4A mux + format dispatch

**Files:**
- Create: `gencast/pipeline/package.py`
- Test: `tests/component/test_package.py`

ffmpeg command for M4A with embedded subtitles (spec §7.4):

```
ffmpeg -y -i audio.mp3 -i subs.srt \
  -map 0:a -map 1:s \
  -c:a aac -b:a 192k \
  -c:s mov_text \
  -metadata:s:s:0 language=eng \
  out.m4a
```

Dispatch (per `Notebook.output.formats`):

| format token | files written |
|---|---|
| `m4a` | `<basename>.m4a` (audio + embedded subs via mov_text) |
| `mp3` | `<basename>.mp3` + `<basename>.srt` (sidecar) |
| `transcript` | `<basename>.transcript.json` |
| `outline` | `<basename>.outline.json` |
| `cost` | `<basename>.cost.json` |

If `m4a` is requested but `ffmpeg` is missing, fall back to mp3+srt with a warning (spec §5.2 row "ffmpeg mux failure").

- [ ] **Step 1: Write the failing tests**

```python
# tests/component/test_package.py
"""Packaging — format dispatch + ffmpeg M4A mux."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gencast.pipeline.package import write_outputs


pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")


@pytest.fixture
def state_with_audio_and_transcript(sample_state_with_transcript, tmp_path):
    from pydub import AudioSegment

    state = sample_state_with_transcript
    state.combined_audio = AudioSegment.silent(duration=1000, frame_rate=44100).set_channels(2)
    # Build minimal clips so SRT building works
    from gencast.pipeline.audio import AudioClip
    state.clips = [
        AudioClip(start_ms=0, end_ms=500, speaker_index=0, speaker_name="Sophie",
                  sentence_text="Hi.", segment_index=0,
                  audio=AudioSegment.silent(duration=500, frame_rate=44100).set_channels(2)),
        AudioClip(start_ms=500, end_ms=1000, speaker_index=1, speaker_name="Ben",
                  sentence_text="Bye.", segment_index=1,
                  audio=AudioSegment.silent(duration=500, frame_rate=44100).set_channels(2)),
    ]
    state.notebook.output.dir = tmp_path
    state.notebook.output.basename = "smoke"
    return state


def test_writes_mp3_with_sidecar(state_with_audio_and_transcript, tmp_path):
    state = state_with_audio_and_transcript
    state.notebook.output.formats = ["mp3"]
    write_outputs(state)
    assert (tmp_path / "smoke.mp3").exists()
    assert (tmp_path / "smoke.srt").exists()


def test_writes_m4a_with_embedded_subs(state_with_audio_and_transcript, tmp_path):
    state = state_with_audio_and_transcript
    state.notebook.output.formats = ["m4a"]
    write_outputs(state)
    out = tmp_path / "smoke.m4a"
    assert out.exists() and out.stat().st_size > 0


def test_writes_json_sidecars(state_with_audio_and_transcript, tmp_path):
    state = state_with_audio_and_transcript
    state.notebook.output.formats = ["transcript", "outline", "cost"]
    write_outputs(state)
    assert (tmp_path / "smoke.transcript.json").exists()
    assert (tmp_path / "smoke.outline.json").exists()
    assert (tmp_path / "smoke.cost.json").exists()


def test_combined_formats(state_with_audio_and_transcript, tmp_path):
    state = state_with_audio_and_transcript
    state.notebook.output.formats = ["m4a", "mp3", "transcript", "cost"]
    write_outputs(state)
    assert (tmp_path / "smoke.m4a").exists()
    assert (tmp_path / "smoke.mp3").exists()
    assert (tmp_path / "smoke.srt").exists()
    assert (tmp_path / "smoke.transcript.json").exists()
    assert (tmp_path / "smoke.cost.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/component/test_package.py -v`
Expected: FAIL with `ImportError` (or skip if ffmpeg absent — that's fine for now).

- [ ] **Step 3: Implement `gencast/pipeline/package.py`**

```python
"""Packaging stage — write requested formats. M4A via ffmpeg with mov_text subs."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from gencast.pipeline.io import (
    write_cost_json,
    write_outline_json,
    write_transcript_json,
)
from gencast.pipeline.subtitles import build_native_srt, srt_format

if TYPE_CHECKING:
    from gencast.pipeline import PodcastState


_FFMPEG = shutil.which("ffmpeg")


def write_outputs(state: "PodcastState") -> dict[str, Path]:
    """Write every format listed in state.notebook.output.formats. Returns paths by format key."""
    out_dir = state.notebook.output.dir
    out_dir.mkdir(parents=True, exist_ok=True)
    base = state.resolved.basename
    formats = set(state.notebook.output.formats)
    written: dict[str, Path] = {}

    needs_mp3 = "m4a" in formats or "mp3" in formats
    needs_srt = "m4a" in formats or "mp3" in formats

    mp3_path = out_dir / f"{base}.mp3"
    srt_path = out_dir / f"{base}.srt"

    if needs_mp3:
        assert state.combined_audio is not None, "combined_audio must be populated"
        state.combined_audio.export(str(mp3_path), format="mp3", bitrate="192k")

    if needs_srt:
        entries = build_native_srt(state.clips, include_speaker=True)
        srt_path.write_text(srt_format(entries))

    if "m4a" in formats:
        m4a_path = out_dir / f"{base}.m4a"
        try:
            _mux_m4a(mp3_path, srt_path, m4a_path)
            written["m4a"] = m4a_path
        except RuntimeError as e:
            print(
                f"[warn] m4a mux failed ({e}); kept mp3+srt sidecars at {mp3_path}.",
                file=sys.stderr,
            )

    if "mp3" in formats:
        written["mp3"] = mp3_path
        written["srt"] = srt_path
    elif "m4a" in formats and "m4a" in written:
        # M4A succeeded; mp3+srt were intermediates → remove unless explicitly requested
        mp3_path.unlink(missing_ok=True)
        srt_path.unlink(missing_ok=True)

    if "transcript" in formats:
        p = out_dir / f"{base}.transcript.json"
        write_transcript_json(state, p)
        written["transcript"] = p

    if "outline" in formats:
        p = out_dir / f"{base}.outline.json"
        write_outline_json(state, p)
        written["outline"] = p

    if "cost" in formats:
        p = out_dir / f"{base}.cost.json"
        write_cost_json(state, p)
        written["cost"] = p

    return written


def _mux_m4a(mp3_path: Path, srt_path: Path, out_path: Path) -> None:
    """Use ffmpeg to mux mp3 + srt → m4a with mov_text embedded subs."""
    if _FFMPEG is None:
        raise RuntimeError("ffmpeg not found on PATH")
    cmd = [
        _FFMPEG, "-y",
        "-i", str(mp3_path),
        "-i", str(srt_path),
        "-map", "0:a", "-map", "1:s",
        "-c:a", "aac", "-b:a", "192k",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {proc.returncode}): {proc.stderr.decode()[-400:]}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/component/test_package.py -v`
Expected: 4 tests pass (or all skipped on systems without ffmpeg).

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/package.py tests/component/test_package.py
git commit -m "Plan B Task 17: package stage — m4a mux + mp3/srt sidecars + JSON outputs"
```

---

### Task B18: Full pipeline orchestrator

**Files:**
- Modify: `gencast/pipeline/__init__.py` (add `run_pipeline`)
- Test: `tests/component/test_pipeline_full.py`

`run_pipeline(notebook)` runs all 10 stages (skipping #4 map-reduce in Plan B; tracked for Plan C). Returns the populated `PodcastState`.

- [ ] **Step 1: Write the failing test**

```python
# tests/component/test_pipeline_full.py
"""End-to-end mocked pipeline — extract, outline, transcript, audio, package."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from gencast.notebook import Notebook
from gencast.pipeline import PodcastState, run_pipeline


@pytest.fixture
def smoke_notebook(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("Sample content. Two sentences here.\n")
    nb = Notebook(
        title="Smoke",
        sources=[str(src)],
        speaker_profile="revision-duo",
        episode_profile="exam-revision",
        room_profile="small-room",
    )
    nb.output.dir = tmp_path / "out"
    nb.output.formats = ["mp3", "transcript", "cost"]  # avoid m4a in mocked test
    return nb


class _FastBackend:
    backend_name = "stub"
    model = "stub-1"
    usd_per_audio_second = 0.0

    async def synthesize(self, *, voice, text):
        from pydub import AudioSegment
        import io
        seg = AudioSegment.silent(duration=120, frame_rate=24000).set_channels(1)
        buf = io.BytesIO()
        seg.export(buf, format="mp3", bitrate="64k")
        return buf.getvalue(), 0.12


def _llm_response(content):
    r = MagicMock()
    r.content = content
    return r


def test_full_pipeline_writes_outputs(smoke_notebook, tmp_path):
    outline_json = '{"segments":[{"name":"Intro","description":"d","size":"short"},{"name":"Wrap","description":"d","size":"short"}]}'
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hello."},{"speaker":"Ben","text":"Bye."}]}'

    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx, \
         patch("gencast.pipeline.get_default_tts_backend") as mock_tts:
        mock_ol.return_value = _llm_response(outline_json)
        mock_tx.return_value = _llm_response(seg_json)
        mock_tts.return_value = _FastBackend()

        state = run_pipeline(smoke_notebook)

    out_dir = smoke_notebook.output.dir
    assert (out_dir / "smoke.mp3").exists()
    assert (out_dir / "smoke.srt").exists()
    assert (out_dir / "smoke.transcript.json").exists()
    assert (out_dir / "smoke.cost.json").exists()
    assert state.combined_audio is not None
    assert len(state.clips) == 4  # 2 segments × 2 turns × 1 sentence each
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/component/test_pipeline_full.py -v`
Expected: FAIL with `ImportError` (`run_pipeline` not defined).

- [ ] **Step 3: Modify `gencast/pipeline/__init__.py`**

Add at the bottom:

```python
from typing import TYPE_CHECKING

from gencast.pipeline.audio import run_audio_stage
from gencast.pipeline.package import write_outputs

if TYPE_CHECKING:
    from gencast.tts import TTSBackend


def get_default_tts_backend(state: PodcastState) -> "TTSBackend":
    """Resolve the default TTS backend from the speaker profile.

    Indirection lets tests patch this single seam instead of monkeypatching
    `get_backend` per-test.
    """
    from gencast.tts import get_backend
    sp = state.resolved.speaker
    return get_backend(sp.tts_provider, sp.tts_model, **(sp.tts_config or {}))


def run_pipeline(notebook: Notebook) -> PodcastState:
    """Full pipeline through packaging. Returns the populated state."""
    import asyncio

    state = run_through_transcript(notebook)
    backend = get_default_tts_backend(state)
    asyncio.run(run_audio_stage(state, backend=backend))
    write_outputs(state)
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/component/test_pipeline_full.py -v`
Expected: 1 test passes.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/__init__.py tests/component/test_pipeline_full.py
git commit -m "Plan B Task 18: run_pipeline — full pipeline through packaging"
```

---

### Task B19: `gencast generate` CLI command + smoke fixture

**Files:**
- Modify: `gencast/cli/main.py`
- Create: `tests/fixtures/notebooks/smoke.yaml`
- Create: `tests/fixtures/notebooks/smoke_source.md`
- Test: `tests/component/test_cli_generate.py`

`gencast generate NB.yaml` — runs `run_pipeline`, prints a per-stage summary at the end.

- [ ] **Step 1: Create the smoke fixture**

```yaml
# tests/fixtures/notebooks/smoke.yaml
title: Smoke Notebook
description: Tiny notebook used by Plan B Task 19 smoke test.
output:
  dir: ./out
  basename: smoke
  formats:
    - mp3
    - transcript
    - cost
sources:
  - smoke_source.md
speaker_profile: revision-duo
episode_profile: exam-revision
room_profile: small-room
overrides:
  num_segments: 3
```

```markdown
# tests/fixtures/notebooks/smoke_source.md

A simple two-sentence source for smoke testing the gencast pipeline.

Photosynthesis converts light energy into chemical energy. Chlorophyll absorbs red and blue wavelengths most strongly.
```

- [ ] **Step 2: Write the failing CLI test**

```python
# tests/component/test_cli_generate.py
"""End-to-end CLI smoke for `gencast generate`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gencast.cli.main import cli


@pytest.fixture
def smoke_notebook_dir(tmp_path):
    """Copy fixtures into a temp dir + rewrite source path to be local."""
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "notebooks"
    src_md = (fixture_dir / "smoke_source.md").read_text()
    nb_yaml = (fixture_dir / "smoke.yaml").read_text()
    (tmp_path / "smoke_source.md").write_text(src_md)
    nb_path = tmp_path / "smoke.yaml"
    nb_path.write_text(nb_yaml)
    return nb_path


class _FastBackend:
    backend_name = "stub"
    model = "stub-1"
    usd_per_audio_second = 0.0

    async def synthesize(self, *, voice, text):
        from pydub import AudioSegment
        import io
        seg = AudioSegment.silent(duration=80, frame_rate=24000).set_channels(1)
        buf = io.BytesIO()
        seg.export(buf, format="mp3", bitrate="64k")
        return buf.getvalue(), 0.08


def _llm(content):
    r = MagicMock()
    r.content = content
    return r


def test_generate_smoke_runs_end_to_end(smoke_notebook_dir, tmp_path):
    outline_json = (
        '{"segments":['
        '{"name":"Intro","description":"d","size":"short"},'
        '{"name":"Body","description":"d","size":"short"},'
        '{"name":"Wrap","description":"d","size":"short"}'
        ']}'
    )
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hi."},{"speaker":"Ben","text":"Bye."}]}'

    runner = CliRunner()
    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx, \
         patch("gencast.pipeline.get_default_tts_backend") as mock_tts:
        mock_ol.return_value = _llm(outline_json)
        mock_tx.return_value = _llm(seg_json)
        mock_tts.return_value = _FastBackend()

        # Notebook output.dir is relative; chdir so it lands in tmp_path
        result = runner.invoke(
            cli, ["generate", str(smoke_notebook_dir)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    # Output directory ./out is relative to cwd, which CliRunner doesn't change.
    # The notebook's NotebookOutput.dir resolves relative to the YAML's parent.
    # We assert on output via the printed summary.
    assert "Wrote" in result.output or "smoke" in result.output
```

- [ ] **Step 3: Modify `gencast/cli/main.py` — add `generate` command**

Append:

```python
from gencast.pipeline import run_pipeline


@cli.command("generate")
@click.argument("notebook_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def generate(notebook_path: Path) -> None:
    """Run the full pipeline: extract → outline → transcript → audio → package."""
    nb = load_notebook(notebook_path)

    # Resolve output.dir relative to notebook file location if it's relative
    if not nb.output.dir.is_absolute():
        nb.output.dir = (notebook_path.parent / nb.output.dir).resolve()

    state = run_pipeline(nb)

    click.secho(f"\n{state.notebook.title}", fg="cyan", bold=True)
    click.echo(f"  speakers:   {state.resolved.speaker.name}")
    click.echo(f"  episode:    {state.resolved.episode.name}")
    click.echo(f"  room:       {state.resolved.room.name}")
    click.echo(f"  source:     {state.source_tokens_original:,} tokens")
    click.echo(f"  outline:    {len(state.outline.segments) if state.outline else 0} segments")
    click.echo(f"  transcript: {len(state.transcript.turns) if state.transcript else 0} turns")
    click.echo(f"  audio:      {len(state.clips)} clips, "
               f"{(len(state.combined_audio) // 1000) if state.combined_audio else 0}s combined")
    click.echo(f"  cost:       ${state.cost.total_usd:.4f}")
    click.secho(f"\nWrote outputs to {nb.output.dir}", fg="green")
```

- [ ] **Step 4: Run all tests**

Run: `./venv/bin/pytest -v`
Expected: all green (or only skipped where ffmpeg/network absent).

- [ ] **Step 5: Manual smoke test (real APIs, opt-in)**

Run (only if you want to spend ~$0.20):

```bash
export OPENAI_API_KEY=$(pass api/openai)
export ANTHROPIC_API_KEY=$(pass api/anthropic)
mkdir -p /tmp/gencast-smoke && cd /tmp/gencast-smoke
cp <repo>/tests/fixtures/notebooks/{smoke.yaml,smoke_source.md} .
./venv/bin/gencast generate smoke.yaml
ls out/
mpv out/smoke.mp3   # or .m4a if you switch formats
```

Expected: produces `out/smoke.mp3`, `out/smoke.srt`, `out/smoke.transcript.json`, `out/smoke.cost.json`. Audio is ~30-60s, no errors.

- [ ] **Step 6: Commit**

```bash
git add gencast/cli/main.py tests/fixtures/notebooks/smoke.yaml tests/fixtures/notebooks/smoke_source.md tests/component/test_cli_generate.py
git commit -m "Plan B Task 19: gencast generate CLI command + smoke notebook fixture"
```

---

## Plan B end-of-phase summary

After all 19 tasks merged into `rewrite/v1.0`, the rewrite has **end-to-end functional parity for normal use**:

- `gencast preview NB.yaml` — outline-only, free (Plan A)
- `gencast generate NB.yaml` — full pipeline, produces `.m4a` with embedded subs by default (Plan B)
- `gencast list-profiles` — three-axis cascade (Plan A)
- 16 bundled profiles (Plan A)
- All 8 locked room presets work end-to-end (Plan B Task 15)
- Anthropic prompt cache wired in for transcript stage (Plan B Tasks 2-3)
- TTS disk cache makes resumption free (Plan B Task 9)
- Sentence-level native SRT, no Whisper round-trip (Plan B Task 16)

What still ships in Plan C: Rich Live UI, `gencast init` wizard, map-reduce for oversize sources, `gencast subtitle` (Whisper STT path), `gencast cache clear`, --cache-llm flag, full test pyramid + CI, end-of-rewrite cutover to `main` → `v1.0.0`.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan B coverage |
|---|---|
| §1 Pipeline stages 6 (transcript), 7 (audio), 8 (combine), 9 (package), 10 (cost) | T3, T10, T15, T17, T5 |
| §2 Module map: pipeline/transcript, tts/, audio_fx/, pipeline/audio, pipeline/subtitles, pipeline/package | T1+T3, T6-T9, T11-T15, T10/T15, T16, T17 |
| §3.1 PodcastState fields: transcript, clips, combined_audio | T4, T10 |
| §3.2 Output artifacts (m4a default, mp3+srt, transcript.json, outline.json, cost.json) | T5, T17 |
| §3.3 CLI: `gencast NB.yaml` (generate) | T19 |
| §4.x Profile schemas | already on trunk; T15 consumes all RoomProfile fields |
| §5.2 Per-stage error matrix | T3 (unknown speaker), T17 (m4a fallback to mp3+srt warn), T10 (tts retry policy via backend `num_retries` is on the backend layer — Plan B uses backends-as-is) |
| §5.4 Resumability via caches | T9 (TTS), T2-3 (Anthropic prompt cache) |
| §6.2 Component & unit tests | every task ships tests |
| §7.2 No-HRTF chain | T11-T15 (verbatim from `scratch/`) |
| §7.4 M4A default with mov_text | T17 |

Gaps:
- LiteLLM retry policy: relies on Plan A's `num_retries=3` already in `chat_completion`. ✅
- TTS retry policy (spec §5.6: 3 retries start=1s factor=2 jitter=0.3): not explicit in B7/B8. Backends inherit retry from `openai` and `httpx` (manual httpx retry would need to be added). For Plan B this is OK — failures bubble up; the spec lists this under "Plan C hardening" via `--retries N`. Captured in Plan C scope.

**2. Placeholder scan:** No "TBD", "TODO", "fill in details", "similar to Task N". Every step has its own code blocks.

**3. Type consistency:** `PodcastState.transcript: Transcript | None`, `state.clips: list[AudioClip]`, `state.combined_audio: AudioSegment | None` — used uniformly across T4, T5, T10, T15, T16, T17, T18, T19. `TTSBackend` Protocol surface (`backend_name`, `model`, `usd_per_audio_second`, `synthesize`) matches across T6, T7, T8, T10. `RoomProfile` field names match the schema in `gencast/profiles/schemas.py` (already on trunk). `OutlineSegment` (existing) is used by T1 jinja prefix and T3 prompt rendering. `chat_completion` cost-meter integration matches Plan A's signature.

---

## Task B20 — Vectorise SchroederReverb (mid-flight v1.0.0 addition)

**Added:** 2026-05-08. Mae's directive: must ship in v1.0.0; blocked a 25-min podcast
from finishing in reasonable time (~20 min wall-clock for reverb alone).

### Problem
`SchroederReverb._comb` and `_allpass` used pure-Python per-sample loops. For a
25-min podcast at 44100 Hz that is ~66 M loop iterations per comb filter. With
4 parallel combs × 2 channels + 2 allpasses, reverb took ~22s for 30s of audio.

### Approach — blockwise numpy (not naive lfilter)
`scipy.signal.lfilter` with a 1300-coefficient sparse IIR array is O(N×D) — just
as slow as the Python loop, because scipy's C backend multiplies every coefficient.
Instead we exploit the *sparse recurrence structure*:

- **Undamped comb:** `B[n] = s[n] + g*B[n-D]` — position n only depends on n-D.
  Processing in chunks of size D reduces each chunk to a single vectorised add:
  `B[start:end] = s[start:end] + g*B[start-D:end-D]`.

- **Damped comb:** adds a 1-pole LPF `L[n] = a*L[n-1] + (1-a)*B[n-D]`. The LPF
  has delay=1 so `scipy.signal.lfilter` handles it fast per chunk, with
  initial-condition propagation (`zi`) carrying state across chunks.

- **Allpass:** `B[n] = s[n] + g*B[n-D]` (same blockwise comb), then
  `y[n] = -g*s[n] + (1-g²)*B[n-D]` (derived algebraically from loop equations).

### Note on lfilter approach
The task brief proposed `lfilter(b,a,x)` with full sparse coefficient arrays.
This is mathematically correct (verified) but O(N×D) — just as slow as the Python
loop for D~1300. The blockwise approach achieves true O(N) with a small constant.

### Results
- **Wall-clock:** 0.47s for 30s stereo audio (with wet LPF) vs ~22s → **~47x speedup**
- **Bit-exact:** max error < 6×10⁻⁸ (float64→float32 rounding noise only)
- **API unchanged:** `SchroederReverb.__init__`, `apply`, all public attributes identical

### Files changed
- `gencast/audio_fx/reverb.py` — `_comb` and `_allpass` replaced with blockwise numpy
- `tests/unit/test_audio_fx_reverb_vectorized.py` — 56 parametrised correctness tests + 1 benchmark
- `pyproject.toml` — registered `benchmark` pytest marker; `addopts = "-m 'not benchmark'"`

Plan B saved. Ready to dispatch.
