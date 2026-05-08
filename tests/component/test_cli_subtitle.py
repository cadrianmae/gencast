"""Whisper subtitle CLI test with mocked OpenAI client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gencast.cli.main import cli


@pytest.fixture
def small_mp3(tmp_path):
    from pydub import AudioSegment
    mp3 = tmp_path / "in.mp3"
    AudioSegment.silent(duration=1000, frame_rate=44100).set_channels(2).export(
        str(mp3), format="mp3", bitrate="128k",
    )
    return mp3


def test_subtitle_writes_srt(small_mp3, tmp_path):
    fake_srt = "1\n00:00:00,000 --> 00:00:01,000\nHello world.\n\n"

    runner = CliRunner()
    with patch("gencast.pipeline.whisper_subtitle.OpenAI") as openai_cls:
        client = openai_cls.return_value
        client.audio.transcriptions.create.return_value = fake_srt
        result = runner.invoke(cli, ["subtitle", str(small_mp3)])
    assert result.exit_code == 0, result.output
    expected = small_mp3.with_suffix(".srt")
    assert expected.exists()
    assert "Hello world" in expected.read_text()
