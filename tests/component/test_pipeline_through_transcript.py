"""Smoke test for run_through_transcript with mocked LLM calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.notebook import Notebook
from gencast.pipeline import PodcastState, run_through_transcript


@pytest.fixture
def smoke_notebook(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("# Sample\n\nSome content.\n")
    return Notebook(
        title="Smoke",
        sources=[str(src)],
        speaker_profile="revision-duo",
        episode_profile="exam-revision",
        room_profile="small-room",
    )


def _mock_llm(content: str):
    r = MagicMock()
    r.content = content
    return r


def test_run_through_transcript_populates_state(smoke_notebook):
    outline_json = '{"segments":[{"name":"Intro","description":"d","size":"short"},{"name":"Wrap","description":"d","size":"short"}]}'
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hi."},{"speaker":"Ben","text":"Hello."}]}'

    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx:
        mock_ol.return_value = _mock_llm(outline_json)
        mock_tx.return_value = _mock_llm(seg_json)

        state = run_through_transcript(smoke_notebook)

    assert isinstance(state, PodcastState)
    assert state.outline is not None
    assert len(state.outline.segments) == 2
    assert state.transcript is not None
    assert len(state.transcript.turns) == 4  # 2 segments × 2 turns each
    # transcript stage was called once per segment
    assert mock_tx.call_count == 2
