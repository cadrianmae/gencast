"""Speaches TTS backend with mocked httpx."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gencast.tts.speaches import SpeachesTTSBackend


@pytest.fixture
def fake_mp3_bytes():
    from pydub import AudioSegment
    seg = AudioSegment.silent(duration=300, frame_rate=24000).set_channels(1)
    import io
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="64k")
    return buf.getvalue()


def test_speaches_synthesize_calls_speech_endpoint(fake_mp3_bytes):
    response = MagicMock()
    response.status_code = 200
    response.content = fake_mp3_bytes
    response.raise_for_status = MagicMock()

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client_cm)
    client_cm.__aexit__ = AsyncMock(return_value=False)
    client_cm.post = AsyncMock(return_value=response)

    with patch("gencast.tts.speaches.httpx.AsyncClient", return_value=client_cm):
        backend = SpeachesTTSBackend(model="kokoro", base_url="http://localhost:8000")
        audio_bytes, seconds = asyncio.run(
            backend.synthesize(voice="af_alloy", text="Hi.")
        )

    assert audio_bytes == fake_mp3_bytes
    assert seconds > 0.2
    call = client_cm.post.await_args
    assert call.args[0].endswith("/v1/audio/speech")
    body = call.kwargs["json"]
    assert body["model"] == "kokoro"
    assert body["voice"] == "af_alloy"
    assert body["input"] == "Hi."


def test_speaches_metadata():
    backend = SpeachesTTSBackend(model="kokoro")
    assert backend.backend_name == "speaches"
    assert backend.model == "kokoro"
    assert backend.usd_per_audio_second == 0.0
