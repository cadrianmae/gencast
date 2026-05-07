"""TTS package — factory + Protocol re-export."""

from __future__ import annotations

from gencast.tts.base import TTSBackend, split_sentences


def get_backend(provider: str, model: str, **config: object) -> TTSBackend:
    """Resolve a TTSBackend by provider name. Imports lazily to keep startup fast."""
    if provider == "openai":
        from gencast.tts.openai import OpenAITTSBackend
        return OpenAITTSBackend(model=model, **config)  # type: ignore[arg-type]
    if provider == "speaches":
        from gencast.tts.speaches import SpeachesTTSBackend
        return SpeachesTTSBackend(model=model, **config)  # type: ignore[arg-type]
    raise ValueError(f"Unknown TTS provider: {provider!r}")


__all__ = ["TTSBackend", "get_backend", "split_sentences"]
