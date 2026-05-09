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
