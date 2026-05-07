"""OpenAI TTS backend with mocked SDK."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from gencast.tts.openai import OpenAITTSBackend


@pytest.fixture
def fake_mp3_bytes():
    """A minimal valid silent mp3 frame (~64 ms). pydub can decode it."""
    # 32 bytes of MPEG-1 Layer III silence header. pydub will load via ffmpeg.
    # Use real silence file in the repo if available; here we pre-render via pydub at test time.
    from pydub import AudioSegment
    seg = AudioSegment.silent(duration=200, frame_rate=24000).set_channels(1)
    import io
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="64k")
    return buf.getvalue()


def _mock_streaming_response(payload: bytes):
    """Mimic openai's with_streaming_response.create context manager."""
    cm = MagicMock()

    def stream_to_file(path):
        from pathlib import Path
        Path(path).write_bytes(payload)

    cm.__enter__.return_value.stream_to_file = stream_to_file
    cm.__exit__.return_value = False
    return cm


def test_openai_tts_returns_bytes_and_seconds(fake_mp3_bytes):
    with patch("gencast.tts.openai.OpenAI") as openai_cls:
        client = openai_cls.return_value
        client.audio.speech.with_streaming_response.create.return_value = (
            _mock_streaming_response(fake_mp3_bytes)
        )

        backend = OpenAITTSBackend(model="tts-1-hd")
        audio_bytes, seconds = asyncio.run(
            backend.synthesize(voice="nova", text="Hello.")
        )
    assert audio_bytes == fake_mp3_bytes
    assert 0.1 < seconds < 0.5


def test_openai_tts_backend_metadata():
    with patch("gencast.tts.openai.OpenAI"):
        backend = OpenAITTSBackend(model="tts-1-hd")
    assert backend.backend_name == "openai"
    assert backend.model == "tts-1-hd"
    # tts-1-hd pricing: $0.030 / 1K chars ~ $0.000234 / second @ 128 chars/sec speaking rate.
    # We only assert it is positive -- exact rate not load-bearing.
    assert backend.usd_per_audio_second > 0
