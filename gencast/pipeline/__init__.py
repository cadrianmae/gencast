"""Pipeline state + orchestrators. Plan B extends through the transcript stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gencast.cost import CostMeter
from gencast.notebook import Notebook, ResolvedNotebook, resolve_notebook
from gencast.pipeline.extract import extract_sources
from gencast.pipeline.outline import Outline, run_outline_stage
from gencast.pipeline.preflight import compress_if_needed
from gencast.pipeline.transcript import Transcript, run_transcript_stage

if TYPE_CHECKING:
    from pydub import AudioSegment
    from gencast.pipeline.audio import AudioClip
    from gencast.tts import TTSBackend


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


from gencast.pipeline.audio import run_audio_stage  # noqa: E402
from gencast.pipeline.package import write_outputs  # noqa: E402


def get_default_tts_backend(state: "PodcastState") -> "TTSBackend":
    """Resolve the default TTS backend from the speaker profile.

    Indirection lets tests patch this single seam instead of monkeypatching
    `get_backend` per-test.
    """
    from gencast.tts import get_backend
    sp = state.resolved.speaker
    return get_backend(sp.tts_provider, sp.tts_model, **(sp.tts_config or {}))


def run_pipeline(notebook: "Notebook") -> "PodcastState":
    """Full pipeline through packaging. Returns the populated state."""
    import asyncio

    state = run_through_transcript(notebook)
    backend = get_default_tts_backend(state)
    asyncio.run(run_audio_stage(state, backend=backend))
    write_outputs(state)
    return state
