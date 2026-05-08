"""End-to-end mocked pipeline — extract, outline, transcript, audio, package."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from gencast.notebook import Notebook
from gencast.pipeline import PodcastState, run_pipeline


@pytest.fixture
def smoke_notebook(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("Sample content. Two sentences here.\n")
    nb = Notebook(
        title="Smoke",
        sources=[str(src)],
        speaker_profile="revision-duo",
        episode_profile="exam-revision",
        room_profile="small-room",
    )
    nb.output.dir = tmp_path / "out"
    nb.output.formats = ["mp3", "transcript", "cost"]  # avoid m4a in mocked test
    return nb


class _FastBackend:
    backend_name = "stub"
    model = "stub-1"
    usd_per_audio_second = 0.0

    async def synthesize(self, *, voice, text):
        from pydub import AudioSegment
        import io
        seg = AudioSegment.silent(duration=120, frame_rate=24000).set_channels(1)
        buf = io.BytesIO()
        seg.export(buf, format="mp3", bitrate="64k")
        return buf.getvalue(), 0.12


def _llm_response(content):
    r = MagicMock()
    r.content = content
    return r


def test_full_pipeline_writes_outputs(smoke_notebook, tmp_path):
    outline_json = '{"segments":[{"name":"Intro","description":"d","size":"short"},{"name":"Wrap","description":"d","size":"short"}]}'
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hello."},{"speaker":"Ben","text":"Bye."}]}'

    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx, \
         patch("gencast.pipeline.get_default_tts_backend") as mock_tts:
        mock_ol.return_value = _llm_response(outline_json)
        mock_tx.return_value = _llm_response(seg_json)
        mock_tts.return_value = _FastBackend()

        state = run_pipeline(smoke_notebook)

    out_dir = smoke_notebook.output.dir
    assert (out_dir / "smoke.mp3").exists()
    assert (out_dir / "smoke.srt").exists()
    assert (out_dir / "smoke.transcript.json").exists()
    assert (out_dir / "smoke.cost.json").exists()
    assert state.combined_audio is not None
    assert len(state.clips) == 4  # 2 segments × 2 turns × 1 sentence each
