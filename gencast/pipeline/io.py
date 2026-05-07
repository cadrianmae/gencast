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
