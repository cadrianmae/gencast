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
CHARS_PER_TRANSCRIPT_TOKEN = 4
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
