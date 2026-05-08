"""Audio stage end-to-end with stub backend."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gencast.pipeline.audio import (
    AudioClip,
    INTER_TURN_PAUSE_MS,
    run_audio_stage,
)
from gencast.pipeline.transcript import Transcript, TranscriptTurn


class StubBackend:
    """Returns 200ms of silence per call. Records calls."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    @property
    def backend_name(self) -> str:
        return "stub"

    @property
    def model(self) -> str:
        return "stub-1"

    @property
    def usd_per_audio_second(self) -> float:
        return 0.001

    async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
        self.calls.append((voice, text))
        from pydub import AudioSegment
        seg = AudioSegment.silent(duration=200, frame_rate=24000).set_channels(1)
        import io
        buf = io.BytesIO()
        seg.export(buf, format="mp3", bitrate="64k")
        return buf.getvalue(), 0.2


def _make_state(transcript_turns):
    """Minimal state factory for the audio stage."""
    from gencast.pipeline.transcript import Transcript
    state = MagicMock()
    state.transcript = Transcript(turns=transcript_turns)

    # Provide only what audio stage needs
    state.resolved.speaker.speakers = [
        MagicMock(name="Sophie", voice_id="nova"),
        MagicMock(name="Ben", voice_id="echo"),
    ]
    # MagicMock auto-name conflicts; explicitly set name attribute:
    state.resolved.speaker.speakers[0].name = "Sophie"
    state.resolved.speaker.speakers[1].name = "Ben"
    state.resolved.speaker.tts_provider = "stub"
    state.resolved.speaker.tts_model = "stub-1"

    state.resolved.room.target_dbfs = -1.0
    state.resolved.room.arc_deg = 120.0
    state.resolved.room.itd_max_ms = 0.6
    state.resolved.room.jitter_deg = 0.0
    state.resolved.room.reverb_wet = 0.0  # disable FX in this test
    state.resolved.room.ambience_db = None
    state.resolved.room.predelay_ms = 20.0
    state.resolved.room.reverb_t60_s = 0.30
    state.resolved.room.reverb_lpf_hz = 2000.0
    state.resolved.room.reverb_damping = 0.55
    state.resolved.room.table_radius_m = 0.85
    state.resolved.room.ambience_lpf_hz = 1500.0
    state.resolved.room.ambience_fan_rumble_db = 4.0

    state.cost = MagicMock()
    state.clips = []
    state.combined_audio = None
    return state


def test_audio_stage_one_turn_per_sentence(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hello there. How are you?", segment_index=0),
        TranscriptTurn(speaker="Ben", text="I'm well.", segment_index=0),
    ])
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))

    # 3 sentences total → 3 clips, 3 backend calls
    assert len(backend.calls) == 3
    assert len(state.clips) == 3
    # Voice routing: speaker name -> voice_id
    assert backend.calls[0] == ("nova", "Hello there.")
    assert backend.calls[1] == ("nova", "How are you?")
    assert backend.calls[2] == ("echo", "I'm well.")


def test_audio_stage_inter_turn_pause(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hi.", segment_index=0),
        TranscriptTurn(speaker="Ben", text="Bye.", segment_index=0),
    ])
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))

    # Two clips at 200ms each + one inter-turn pause
    assert state.clips[0].start_ms == 0
    assert state.clips[0].end_ms == 200
    assert state.clips[1].start_ms == 200 + INTER_TURN_PAUSE_MS
    assert state.clips[1].end_ms == 200 + INTER_TURN_PAUSE_MS + 200


def test_audio_stage_caches_misses(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Same text.", segment_index=0),
        TranscriptTurn(speaker="Sophie", text="Same text.", segment_index=0),
    ])
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))
    # Second call hits the cache
    assert len(backend.calls) == 1


def test_audio_stage_records_cost(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="One.", segment_index=0),
        TranscriptTurn(speaker="Ben", text="Two.", segment_index=0),
    ])
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))
    state.cost.record_tts.assert_called()
    # Total seconds across all calls = 2 × 0.2 = 0.4
    total_seconds = sum(
        c.kwargs["audio_seconds"] for c in state.cost.record_tts.call_args_list
    )
    assert abs(total_seconds - 0.4) < 0.01
