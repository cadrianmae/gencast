"""Speaches TTS backend — OpenAI-compatible endpoint, httpx-based."""

from __future__ import annotations

import io
import os

import httpx
from pydub import AudioSegment


class SpeachesTTSBackend:
    """POST /v1/audio/speech to a Speaches-compatible server."""

    def __init__(
        self,
        *,
        model: str = "kokoro",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        self._model = model
        self._base_url = (base_url or os.environ.get("SPEACHES_BASE_URL")
                         or "http://localhost:8000").rstrip("/")
        self._api_key = api_key or os.environ.get("SPEACHES_API_KEY") or ""
        self._timeout = timeout

    @property
    def backend_name(self) -> str:
        return "speaches"

    @property
    def model(self) -> str:
        return self._model

    @property
    def usd_per_audio_second(self) -> float:
        return 0.0  # Self-hosted by default; if using a paid Speaches host, override here.

    async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
        url = f"{self._base_url}/v1/audio/speech"
        body = {"model": self._model, "voice": voice, "input": text, "response_format": "mp3"}
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            audio_bytes = resp.content

        seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        seconds = len(seg) / 1000.0
        return audio_bytes, seconds
