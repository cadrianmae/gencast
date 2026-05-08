"""Each stage calls reporter — verify state transitions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.notebook import Notebook
from gencast.pipeline import run_pipeline


@pytest.fixture
def smoke_notebook(tmp_path):
    src = tmp_path / "s.md"
    src.write_text("Some content here. Two sentences total.\n")
    nb = Notebook(
        title="Smoke",
        sources=[str(src)],
        speaker_profile="revision-duo",
        episode_profile="exam-revision",
        room_profile="small-room",
    )
    nb.output.dir = tmp_path / "out"
    nb.output.formats = ["mp3", "transcript", "cost"]
    return nb


class _FastBackend:
    backend_name = "stub"
    model = "stub-1"
    usd_per_audio_second = 0.0
    async def synthesize(self, *, voice, text):
        from pydub import AudioSegment
        import io
        seg = AudioSegment.silent(duration=80, frame_rate=24000).set_channels(1)
        buf = io.BytesIO(); seg.export(buf, format="mp3", bitrate="64k")
        return buf.getvalue(), 0.08


def _llm(content):
    r = MagicMock(); r.content = content; return r


def test_reporter_sees_stages_2_5_6_7(smoke_notebook):
    reporter = MagicMock()
    outline_json = '{"segments":[{"name":"a","description":"d","size":"short"},{"name":"b","description":"d","size":"short"}]}'
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hi."},{"speaker":"Ben","text":"Bye."}]}'

    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx, \
         patch("gencast.pipeline.get_default_tts_backend") as mock_tts:
        mock_ol.return_value = _llm(outline_json)
        mock_tx.return_value = _llm(seg_json)
        mock_tts.return_value = _FastBackend()
        run_pipeline(smoke_notebook, reporter=reporter)

    # Each stage called stage_start at least once
    starts = [c for c in reporter.method_calls if c[0] == "stage_start"]
    stage_indices = {c.args[0] for c in starts}
    # Extract (2), Outline (5), Transcript (6), Audio (7), Package (9) — at minimum
    assert {2, 5, 6, 7, 9}.issubset(stage_indices)


def test_run_pipeline_works_without_reporter(smoke_notebook):
    """Reporter must be optional — backwards compat with run_pipeline(notebook)."""
    outline_json = '{"segments":[{"name":"a","description":"d","size":"short"}]}'
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hi."}]}'

    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx, \
         patch("gencast.pipeline.get_default_tts_backend") as mock_tts:
        mock_ol.return_value = _llm(outline_json)
        mock_tx.return_value = _llm(seg_json)
        mock_tts.return_value = _FastBackend()
        state = run_pipeline(smoke_notebook)  # no reporter kwarg
    assert state is not None
