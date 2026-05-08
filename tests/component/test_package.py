"""Packaging — format dispatch + ffmpeg M4A mux."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gencast.pipeline.package import write_outputs


pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")


@pytest.fixture
def state_with_audio_and_transcript(sample_state_with_transcript, tmp_path):
    from pydub import AudioSegment

    state = sample_state_with_transcript
    state.combined_audio = AudioSegment.silent(duration=1000, frame_rate=44100).set_channels(2)
    # Build minimal clips so SRT building works
    from gencast.pipeline.audio import AudioClip
    state.clips = [
        AudioClip(start_ms=0, end_ms=500, speaker_index=0, speaker_name="Sophie",
                  sentence_text="Hi.", segment_index=0,
                  audio=AudioSegment.silent(duration=500, frame_rate=44100).set_channels(2)),
        AudioClip(start_ms=500, end_ms=1000, speaker_index=1, speaker_name="Ben",
                  sentence_text="Bye.", segment_index=1,
                  audio=AudioSegment.silent(duration=500, frame_rate=44100).set_channels(2)),
    ]
    state.notebook.output.dir = tmp_path
    state.notebook.output.basename = "smoke"
    return state


def test_writes_mp3_with_sidecar(state_with_audio_and_transcript, tmp_path):
    state = state_with_audio_and_transcript
    state.notebook.output.formats = ["mp3"]
    write_outputs(state)
    assert (tmp_path / "smoke.mp3").exists()
    assert (tmp_path / "smoke.srt").exists()


def test_writes_m4a_with_embedded_subs(state_with_audio_and_transcript, tmp_path):
    state = state_with_audio_and_transcript
    state.notebook.output.formats = ["m4a"]
    write_outputs(state)
    out = tmp_path / "smoke.m4a"
    assert out.exists() and out.stat().st_size > 0


def test_writes_json_sidecars(state_with_audio_and_transcript, tmp_path):
    state = state_with_audio_and_transcript
    state.notebook.output.formats = ["transcript", "outline", "cost"]
    write_outputs(state)
    assert (tmp_path / "smoke.transcript.json").exists()
    assert (tmp_path / "smoke.outline.json").exists()
    assert (tmp_path / "smoke.cost.json").exists()


def test_combined_formats(state_with_audio_and_transcript, tmp_path):
    state = state_with_audio_and_transcript
    state.notebook.output.formats = ["m4a", "mp3", "transcript", "cost"]
    write_outputs(state)
    assert (tmp_path / "smoke.m4a").exists()
    assert (tmp_path / "smoke.mp3").exists()
    assert (tmp_path / "smoke.srt").exists()
    assert (tmp_path / "smoke.transcript.json").exists()
    assert (tmp_path / "smoke.cost.json").exists()
