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
