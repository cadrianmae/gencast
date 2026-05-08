"""TTSBackend Protocol + sentence splitter shared across backends."""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

# Based on scratch/spatial_test.py; extended to handle closing quotes before
# the gap (e.g. 'She said "Hi." Then she left.' splits into 2 sentences).
_SENT_RE = re.compile(r'(?<=[.!?])["\']?\s+(?=[A-Z"\'])')


def split_sentences(text: str) -> list[str]:
    """Split text into sentences. Always returns at least one element."""
    parts = [p.strip() for p in _SENT_RE.split(text) if p.strip()]
    return parts or [text]


@runtime_checkable
class TTSBackend(Protocol):
    """Minimal surface every TTS backend implements.

    Returns mp3 bytes (not wav, not pydub) so caches can store the raw stream
    untouched. Audio loaders convert via pydub later.
    """

    @property
    def backend_name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def usd_per_audio_second(self) -> float: ...

    async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
        """Return (mp3_bytes, audio_seconds)."""
        ...
