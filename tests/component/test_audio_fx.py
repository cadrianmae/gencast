"""Audio FX integration in the audio stage. Reuses StubBackend from B10."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from gencast.pipeline.audio import run_audio_stage
from gencast.pipeline.transcript import TranscriptTurn

# Import the stub backend used in test_audio_stage
from tests.component.test_audio_stage import StubBackend, _make_state


def test_apply_room_produces_stereo_output(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hello.", segment_index=0),
        TranscriptTurn(speaker="Ben", text="Hi.", segment_index=0),
    ])
    # Re-enable FX (B10 test had wet=0). Apply moderate values.
    state.resolved.room.reverb_wet = 0.05
    state.resolved.room.ambience_db = -70.0

    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))

    assert state.combined_audio is not None
    assert state.combined_audio.channels == 2
    # All clips stereo too
    for c in state.clips:
        assert c.audio.channels == 2


def test_zero_wet_skips_reverb(tmp_path):
    """When reverb_wet=0, render_clip_with_room should still produce stereo."""
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hi.", segment_index=0),
    ])
    state.resolved.room.reverb_wet = 0.0
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))
    assert state.clips[0].audio.channels == 2


def test_ambience_disabled_when_db_none(tmp_path):
    state = _make_state([
        TranscriptTurn(speaker="Sophie", text="Hi.", segment_index=0),
    ])
    state.resolved.room.reverb_wet = 0.0
    state.resolved.room.ambience_db = None
    backend = StubBackend()
    asyncio.run(run_audio_stage(state, backend=backend, cache_dir=tmp_path))
    # Just check it ran without raising and produced output
    assert state.combined_audio is not None
