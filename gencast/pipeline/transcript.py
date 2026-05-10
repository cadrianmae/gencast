"""Per-segment transcript stage — model + jinja rendering. Executor follows in Task B3."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

from gencast.pipeline.stream_filter import JsonObjectStreamFilter, transcript_turn_emitter

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


import json
import re
from typing import TYPE_CHECKING

from gencast.cost import CostMeter
from gencast.llm import chat_completion
from gencast.llm.caching import build_cached_messages
from gencast.pipeline.outline import Outline

if TYPE_CHECKING:
    from gencast.logger import Reporter


# Same code-fence stripper as outline stage. Keep local to avoid cross-module import cycle.
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_code_fence(s: str) -> str:
    m = _FENCE_RE.match(s)
    return m.group(1) if m else s


# Backward-compat shim — older imports + the v1.3.1 unit tests use this name.
class _TurnStreamFilter:
    """Schema-aware streaming filter for transcript JSON. Emits one
    'Speaker: text\\n' line per complete turn object as the stream arrives.
    """

    def __init__(self, emit: Callable[[str], None]):
        self._inner = JsonObjectStreamFilter(transcript_turn_emitter(emit))

    def feed(self, chunk: str) -> None:
        self._inner.feed(chunk)


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
    reporter: "Reporter | None" = None,
) -> Transcript:
    """Loop outline segments, one LLM call each, accumulate turns into a Transcript."""
    valid_speaker_names = {s.name for s in speakers}
    all_turns: list[TranscriptTurn] = []

    if reporter is not None:
        reporter.stage_start(6, 10, "Transcript", total_items=len(outline.segments))

    for seg_index in range(len(outline.segments)):
        prefix, suffix = render_transcript_segment_prompt(
            briefing=briefing, content=content, speakers=speakers,
            outline_segments=outline.segments, segment_index=seg_index,
            language=language,
        )
        messages = build_cached_messages(
            provider=transcript_provider, prefix=prefix, suffix=suffix,
        )
        # Retry the segment on JSON parse failure — LLMs occasionally truncate
        # mid-string or emit malformed JSON even with response_format=json_object.
        # Each attempt is a fresh API call (not cheap), so cap at 3 total tries.
        last_raw = ""
        last_err: Exception | None = None
        data = None
        response = None
        for attempt in range(3):
            on_chunk: Callable[[str], None] | None = None
            if reporter is not None:
                reporter.stream_open(
                    title=(f"transcript segment {seg_index + 1}/{len(outline.segments)}"
                           + (f" (retry {attempt})" if attempt else "")),
                    mode="rolling",
                    max_lines=5,
                )
                on_chunk = _TurnStreamFilter(reporter.stream_chunk).feed
            response = chat_completion(
                provider=transcript_provider,
                model=transcript_model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=12000,
                cost_meter=cost_meter,
                stage="transcript",
                on_chunk=on_chunk,
            )
            if reporter is not None:
                reporter.stream_close()

            last_raw = _strip_code_fence(response.content)
            try:
                data = json.loads(last_raw)
                break
            except json.JSONDecodeError as e:
                last_err = e
                if reporter is not None:
                    reporter.warn(
                        f"Transcript segment {seg_index + 1} attempt {attempt + 1} "
                        f"returned malformed JSON ({e}); retrying…"
                    )
                continue

        if data is None:
            raise ValueError(
                f"Transcript segment {seg_index + 1} returned non-JSON after 3 attempts: "
                f"{last_err}. Raw (last attempt, first 300 chars): {last_raw[:300]!r}"
            ) from last_err

        if reporter is not None and response is not None:
            try:
                tokens_in = int(response.tokens_in)
                cache_reads_in = int(response.cache_reads_in)
            except (TypeError, ValueError):
                tokens_in = 0
                cache_reads_in = 0
            cache_pct = 0.0
            if tokens_in > 0:
                cache_pct = 100.0 * cache_reads_in / tokens_in
            reporter.stage_activity(
                f"[{transcript_provider}/{transcript_model}] segment {seg_index + 1} — "
                f"cache read {cache_pct:.0f}% ({cache_reads_in} of {tokens_in} tok)"
            )
            reporter.stage_advance(1)

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

    if reporter is not None:
        reporter.stage_done()

    return Transcript(turns=all_turns)
