"""Per-stage cost tracking — tokens, audio seconds, USD."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageCost:
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
        if name not in self.stages:
            self.stages[name] = StageCost(kind=kind)
        return self.stages[name]

    def record_llm(
        self, stage: str, *, model: str,
        tokens_in: int, tokens_out: int,
        cache_reads_in: int = 0, cache_writes_in: int = 0,
        usd: float,
    ) -> None:
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
        s = self._stage(stage, "tts")
        s.backend = backend
        s.model = model
        s.audio_seconds += audio_seconds
        s.usd += usd

    @property
    def total_usd(self) -> float:
        return sum(s.usd for s in self.stages.values())

    def to_dict(self) -> dict[str, Any]:
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
