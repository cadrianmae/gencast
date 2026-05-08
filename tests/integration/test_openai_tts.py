"""Real OpenAI TTS — env-gated."""

from __future__ import annotations

import asyncio
import io
import os

import pytest
from pydub import AudioSegment

from gencast.tts.openai import OpenAITTSBackend

pytestmark = pytest.mark.skipif(
    os.environ.get("GENCAST_TEST_OPENAI") != "1",
    reason="GENCAST_TEST_OPENAI=1 not set",
)


def test_openai_tts_real_roundtrip():
    backend = OpenAITTSBackend(model="tts-1")  # cheaper than tts-1-hd for tests
    audio_bytes, seconds = asyncio.run(
        backend.synthesize(voice="nova", text="The quick brown fox jumps.")
    )
    assert len(audio_bytes) > 1000
    seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    assert len(seg) > 500  # > 0.5s
    assert abs(len(seg) / 1000.0 - seconds) < 0.5
