"""Per-stage cost tracking — tokens, audio seconds, USD."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageCost:
    """Per-stage cost slot. Numeric fields accumulate across multiple calls."""
    kind: str  # "llm" | "tts"
    model: str | None = None
    backend: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cache_reads_in: int = 0
    cache_writes_in: int = 0
    audio_seconds: float = 0.0
    usd: float = 0.0


@dataclass
class CostMeter:
    """Accumulates per-stage costs across a pipeline run."""
    stages: dict[str, StageCost] = field(default_factory=dict)

    def _stage(self, name: str, kind: str) -> StageCost:
        if name in self.stages:
            existing = self.stages[name]
            if existing.kind != kind:
                raise ValueError(
                    f"Stage '{name}' was registered as '{existing.kind}' but called with kind='{kind}'."
                )
            return existing
        self.stages[name] = StageCost(kind=kind)
        return self.stages[name]

    def record_llm(
        self, stage: str, *, model: str,
        tokens_in: int, tokens_out: int,
        cache_reads_in: int = 0, cache_writes_in: int = 0,
        usd: float,
    ) -> None:
        """Accumulate one LLM call's usage into the named stage. Stage must be 'llm' kind."""
        s = self._stage(stage, "llm")
        s.model = model
        s.tokens_in += tokens_in
        s.tokens_out += tokens_out
        s.cache_reads_in += cache_reads_in
        s.cache_writes_in += cache_writes_in
        s.usd += usd

    def record_tts(
        self, stage: str, *, backend: str, model: str,
        audio_seconds: float, usd: float,
    ) -> None:
        """Accumulate one TTS call's audio_seconds + cost into the named stage."""
        s = self._stage(stage, "tts")
        s.backend = backend
        s.model = model
        s.audio_seconds += audio_seconds
        s.usd += usd

    @property
    def total_usd(self) -> float:
        return sum(s.usd for s in self.stages.values())

    def to_dict(self) -> dict[str, Any]:
        """Serialise all per-stage data + total_usd as plain dict (JSON-friendly)."""
        return {
            "stages": {
                name: {
                    "kind": s.kind,
                    "model": s.model,
                    "backend": s.backend,
                    "tokens_in": s.tokens_in,
                    "tokens_out": s.tokens_out,
                    "cache_reads_in": s.cache_reads_in,
                    "cache_writes_in": s.cache_writes_in,
                    "audio_seconds": s.audio_seconds,
                    "usd": s.usd,
                }
                for name, s in self.stages.items()
            },
            "total_usd": self.total_usd,
        }
