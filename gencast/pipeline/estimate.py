# gencast/pipeline/estimate.py
"""Cost estimation for a notebook — preflight prediction without running the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

StageName = Literal["extract", "outline", "transcript", "tts", "whisper"]


@dataclass(frozen=True)
class StageEstimate:
    """Per-stage cost prediction. Fields not relevant to a stage stay at their defaults."""
    stage: StageName
    provider: str | None
    model: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    characters: int = 0          # tts only
    duration_minutes: float = 0.0  # whisper only
    usd: float = 0.0


@dataclass(frozen=True)
class Suggestion:
    """A cheaper-model alternative for one stage."""
    stage: str
    current: str               # "provider/model"
    alternative: str
    saves_usd: float
    saves_pct: int
    trade_off: str             # "quality" | "speed" | "..."


@dataclass(frozen=True)
class Estimate:
    """Full notebook cost prediction with per-stage breakdown and optional suggestions."""
    notebook_path: Path
    source_tokens: int
    stages: list[StageEstimate]
    total_usd: float
    uncertainty_pct: int = 25
    suggestions: list[Suggestion] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Heuristic constants — see spec for sources.
# ---------------------------------------------------------------------------

OUTLINE_OUTPUT_TOKENS = 600
WORDS_PER_SEGMENT = 150
TOKENS_PER_WORD = 1.5
WORDS_PER_MINUTE = 150

OPENAI_TTS_HD_PER_1K_CHARS = 0.030
OPENAI_TTS_STD_PER_1K_CHARS = 0.015
OPENAI_WHISPER_PER_MINUTE = 0.006

LOCAL_PROVIDERS = frozenset({"ollama", "speaches"})


@dataclass(frozen=True)
class _ModelRate:
    input_per_1k: float
    output_per_1k: float


def _lookup_rate(provider: str, model: str) -> "_ModelRate | None":
    """Look up per-1k-token USD rate for a provider/model.

    Source of truth is ``litellm.model_cost`` — the same dict gencast uses
    at runtime via ``response_cost``. Local providers (ollama, speaches)
    return a zero rate without consulting litellm.

    Returns None if the model is unknown.
    """
    if provider in LOCAL_PROVIDERS:
        return _ModelRate(0.0, 0.0)

    import litellm  # noqa: PLC0415 — deferred to avoid slow import at module load
    full_key = f"{provider}/{model}"
    entry = litellm.model_cost.get(full_key) or litellm.model_cost.get(model)
    if entry is None:
        return None
    inp = entry.get("input_cost_per_token")
    out = entry.get("output_cost_per_token")
    if inp is None or out is None:
        return None
    return _ModelRate(input_per_1k=inp * 1000, output_per_1k=out * 1000)


def _estimate_outline(*, provider: str, model: str, source_tokens: int) -> StageEstimate:
    """Outline stage: full source + small structured output."""
    rate = _lookup_rate(provider, model)
    usd = 0.0
    if rate is not None:
        usd = (
            (source_tokens / 1000) * rate.input_per_1k
            + (OUTLINE_OUTPUT_TOKENS / 1000) * rate.output_per_1k
        )
    return StageEstimate(
        stage="outline",
        provider=provider,
        model=model,
        input_tokens=source_tokens,
        output_tokens=OUTLINE_OUTPUT_TOKENS,
        usd=round(usd, 4),
    )


def _estimate_transcript(
    *, provider: str, model: str, source_tokens: int, num_segments: int,
) -> StageEstimate:
    """Transcript stage: full source as input per segment (prompt caching makes
    the cached prefix cheap, but we estimate without cache awareness — see spec
    Edge Cases). Output tokens scale with segments * words/segment.
    """
    output_tokens = int(num_segments * WORDS_PER_SEGMENT * TOKENS_PER_WORD)
    rate = _lookup_rate(provider, model)
    usd = 0.0
    if rate is not None:
        usd = (
            (source_tokens / 1000) * rate.input_per_1k
            + (output_tokens / 1000) * rate.output_per_1k
        )
    return StageEstimate(
        stage="transcript",
        provider=provider,
        model=model,
        input_tokens=source_tokens,
        output_tokens=output_tokens,
        usd=round(usd, 4),
    )


# Average English chars-per-word including spaces/punctuation
_CHARS_PER_WORD = 5.0


def _estimate_tts(*, provider: str, model: str, num_segments: int) -> StageEstimate:
    """TTS: characters = num_segments × words/segment × chars/word. Rate
    depends on model (HD vs std vs local).
    """
    characters = int(num_segments * WORDS_PER_SEGMENT * _CHARS_PER_WORD)
    if provider in LOCAL_PROVIDERS:
        usd = 0.0
    elif "hd" in (model or "").lower():
        usd = (characters / 1000) * OPENAI_TTS_HD_PER_1K_CHARS
    else:
        usd = (characters / 1000) * OPENAI_TTS_STD_PER_1K_CHARS
    return StageEstimate(
        stage="tts",
        provider=provider,
        model=model,
        characters=characters,
        usd=round(usd, 4),
    )


def _estimate_whisper(*, num_segments: int) -> StageEstimate:
    """Whisper: duration ≈ words spoken / words-per-minute. Rate is a
    fixed OpenAI per-minute charge.
    """
    duration_minutes = (num_segments * WORDS_PER_SEGMENT) / WORDS_PER_MINUTE
    usd = duration_minutes * OPENAI_WHISPER_PER_MINUTE
    return StageEstimate(
        stage="whisper",
        provider="openai",
        model="whisper-1",
        duration_minutes=round(duration_minutes, 2),
        usd=round(usd, 4),
    )


def estimate_notebook(nb: object) -> Estimate:
    """Predict total USD cost for running this notebook. Reads source
    files (no LLM calls), token-counts via tiktoken, projects output
    using heuristic constants, looks up rates via litellm.model_cost.
    """
    from gencast.notebook import Notebook, resolve_notebook
    from gencast.pipeline.extract import extract_sources

    assert isinstance(nb, Notebook)
    resolved = resolve_notebook(nb)

    # Resolve source paths relative to the notebook file (if available).
    notebook_dir = getattr(nb, "_source_path", Path("."))
    if isinstance(notebook_dir, Path) and notebook_dir.is_file():
        notebook_dir = notebook_dir.parent
    else:
        notebook_dir = Path(".")
    sources = [
        notebook_dir / s if not Path(s).is_absolute() else Path(s)
        for s in nb.sources
    ]

    _source_text, source_tokens = extract_sources(
        sources,
        model=f"{resolved.outline_provider}/{resolved.outline_model}",
    )

    # Extract is always $0 (local file I/O + tiktoken)
    extract_stage = StageEstimate(
        stage="extract", provider=None, model=None, usd=0.0,
    )

    outline = _estimate_outline(
        provider=resolved.outline_provider,
        model=resolved.outline_model,
        source_tokens=source_tokens,
    )
    transcript = _estimate_transcript(
        provider=resolved.transcript_provider,
        model=resolved.transcript_model,
        source_tokens=source_tokens,
        num_segments=resolved.num_segments,
    )
    tts = _estimate_tts(
        provider=resolved.speaker.tts_provider,
        model=resolved.speaker.tts_model,
        num_segments=resolved.num_segments,
    )
    whisper = _estimate_whisper(num_segments=resolved.num_segments)

    stages = [extract_stage, outline, transcript, tts, whisper]
    total = round(sum(s.usd for s in stages), 4)

    notebook_path = getattr(nb, "_source_path", Path("(unsaved)"))
    return Estimate(
        notebook_path=notebook_path,
        source_tokens=source_tokens,
        stages=stages,
        total_usd=total,
    )
