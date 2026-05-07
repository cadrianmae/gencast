"""Disk-backed TTS cache (always on; deterministic + expensive workload)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


class TTSDiskCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, *, provider: str, model: str, voice: str, text: str) -> Path:
        key = hashlib.sha256(
            f"{provider}|{model}|{voice}|{text}".encode()
        ).hexdigest()[:24]
        return self.root / provider / model / voice / f"{key}.mp3"

    def get(self, *, provider: str, model: str, voice: str, text: str) -> bytes | None:
        p = self._path(provider=provider, model=model, voice=voice, text=text)
        if p.exists():
            return p.read_bytes()
        return None

    def put(
        self, *, provider: str, model: str, voice: str, text: str, audio_bytes: bytes,
    ) -> None:
        p = self._path(provider=provider, model=model, voice=voice, text=text)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(audio_bytes)


def default_cache_dir() -> Path:
    """XDG-compliant default cache directory."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "gencast" / "tts"
