"""Pipeline state + orchestrator. Plan A only goes through the outline stage."""

from __future__ import annotations

from dataclasses import dataclass, field

from gencast.cost import CostMeter
from gencast.notebook import Notebook, ResolvedNotebook, resolve_notebook
from gencast.pipeline.extract import extract_sources
from gencast.pipeline.outline import Outline, run_outline_stage
from gencast.pipeline.preflight import preflight


@dataclass
class PodcastState:
    notebook: Notebook
    resolved: ResolvedNotebook
    source_text: str = ""
    source_tokens_original: int = 0
    source_tokens_final: int = 0
    outline: Outline | None = None
    cost: CostMeter = field(default_factory=CostMeter)


def run_through_outline(notebook: Notebook) -> PodcastState:
    """Plan A pipeline: load → extract → preflight → outline. Returns the state."""
    resolved = resolve_notebook(notebook)
    state = PodcastState(notebook=notebook, resolved=resolved)

    # Stage 2: extract
    text, tokens = extract_sources(
        notebook.sources,
        model=f"{resolved.outline_provider}/{resolved.outline_model}",
    )
    state.source_text = text
    state.source_tokens_original = tokens
    state.source_tokens_final = tokens  # no map-reduce in Plan A

    # Stage 3: preflight
    preflight(
        source_tokens=tokens,
        model=f"{resolved.outline_provider}/{resolved.outline_model}",
    )

    # Stage 5: outline (Plan A skips stage 4 map-reduce)
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
