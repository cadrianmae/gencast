"""Pipeline state + orchestrators. Plan B extends through the transcript stage."""

from __future__ import annotations

import datetime as _dt
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from gencast.cost import CostMeter


def new_session_id() -> str:
    """Generate a unique-enough session ID for tracking a single `gencast generate` run."""
    return f"{_dt.datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


def session_log_path(session_id: str) -> Path:
    """Where the session log lives. Honours XDG_CACHE_HOME."""
    base = Path(os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache"))
    return base / "gencast" / "sessions" / f"{session_id}.log"
from gencast.notebook import Notebook, ResolvedNotebook, resolve_notebook
from gencast.pipeline.extract import extract_sources
from gencast.pipeline.outline import Outline, run_outline_stage
from gencast.pipeline.preflight import compress_if_needed
from gencast.pipeline.transcript import Transcript, run_transcript_stage

if TYPE_CHECKING:
    from pydub import AudioSegment
    from gencast.logger import Reporter
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


def _run_load_extract_preflight_outline(
    notebook: Notebook, *, reporter: "Reporter | None" = None,
) -> PodcastState:
    """Stages 1, 2, 3, 5. (4 = map-reduce, deferred to Plan C.)"""
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
        reporter=reporter,
    )
    return state


def run_through_outline(notebook: Notebook, *, reporter: "Reporter | None" = None) -> PodcastState:
    """Plan A pipeline: load → extract → preflight → outline. Used by `gencast preview`."""
    return _run_load_extract_preflight_outline(notebook, reporter=reporter)


def run_through_transcript(notebook: Notebook, *, reporter: "Reporter | None" = None) -> PodcastState:
    """Plan A pipeline + transcript stage. Used by Plan B/C orchestrators."""
    state = _run_load_extract_preflight_outline(notebook, reporter=reporter)
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
        reporter=reporter,
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


def run_pipeline(notebook: "Notebook", *, reporter: "Reporter | None" = None) -> "PodcastState":
    """Full pipeline through packaging. Returns the populated state."""
    import asyncio

    # Open a session log file under ~/.cache/gencast/sessions/<id>.log and
    # tee all reporter events to it.
    session_id = new_session_id()
    log_path = session_log_path(session_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"# gencast session {session_id}\n"
        f"# started: {_dt.datetime.now().isoformat()}\n"
        f"# notebook: {notebook.title}\n"
        f"# resolved: speaker={notebook.speaker_profile or '(default)'} "
        f"episode={notebook.episode_profile or '(default)'} "
        f"room={notebook.room_profile or '(default)'}\n"
    )
    if reporter is not None:
        reporter.set_log_sink(log_path)
        reporter.info(f"session: {session_id}  log: {log_path}")

    state = run_through_transcript(notebook, reporter=reporter)
    backend = get_default_tts_backend(state)
    asyncio.run(run_audio_stage(state, backend=backend, reporter=reporter))

    if reporter is not None:
        reporter.stage_start(9, 10, "Package")
        reporter.stage_activity(f"writing formats: {state.notebook.output.formats}")
    write_outputs(state)
    if reporter is not None:
        reporter.stage_done()
        close = getattr(reporter, "close", None)
        if close is not None:
            close()

    return state
