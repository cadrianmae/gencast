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
