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
