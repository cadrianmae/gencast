"""OpenAI TTS backend (tts-1, tts-1-hd)."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from openai import OpenAI
from pydub import AudioSegment

# OpenAI tts-1-hd pricing as of 2026: $0.030 / 1K input characters.
# At ~128 chars/sec speaking rate this is ~$0.000234 / audio second.
# We approximate via audio_seconds for cost-meter compatibility.
_USD_PER_SEC = {
    "tts-1": 0.000117,
    "tts-1-hd": 0.000234,
}


class OpenAITTSBackend:
    """Synchronous OpenAI client wrapped in async surface (offload via asyncio.to_thread)."""

    def __init__(self, *, model: str = "tts-1-hd", api_key: str | None = None):
        self._model = model
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    @property
    def backend_name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    @property
    def usd_per_audio_second(self) -> float:
        return _USD_PER_SEC.get(self._model, 0.000234)

    async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
        import asyncio
        return await asyncio.to_thread(self._synthesize_blocking, voice, text)

    def _synthesize_blocking(self, voice: str, text: str) -> tuple[bytes, float]:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp = Path(f.name)
        try:
            with self._client.audio.speech.with_streaming_response.create(
                model=self._model, voice=voice, input=text,
            ) as resp:
                resp.stream_to_file(str(tmp))
            audio_bytes = tmp.read_bytes()
            seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
            seconds = len(seg) / 1000.0
            return audio_bytes, seconds
        finally:
            tmp.unlink(missing_ok=True)
