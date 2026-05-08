"""Component tests for the per-segment transcript stage with mocked LLM."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.pipeline.outline import Outline, OutlineSegment
from gencast.pipeline.transcript import (
    Transcript,
    TranscriptTurn,
    run_transcript_stage,
)
from gencast.profiles.schemas import Speaker


@pytest.fixture
def speakers():
    return [
        Speaker(name="Sophie", voice_id="nova", backstory="bg", personality="p"),
        Speaker(name="Ben", voice_id="echo", backstory="bg", personality="p"),
    ]


@pytest.fixture
def outline():
    return Outline(segments=[
        OutlineSegment(name="Intro", description="d", size="short"),
        OutlineSegment(name="Body", description="d", size="medium"),
        OutlineSegment(name="Wrap", description="d", size="short"),
    ])


def _mock_response(json_str: str):
    resp = MagicMock()
    resp.content = json_str
    return resp


def test_run_transcript_stage_loops_segments(speakers, outline, cost_meter):
    """3 segments → 3 LLM calls → 3 transcripts concatenated."""
    seg_responses = [
        '{"turns":[{"speaker":"Sophie","text":"Hi all."},{"speaker":"Ben","text":"Hello."}]}',
        '{"turns":[{"speaker":"Sophie","text":"Body 1."},{"speaker":"Ben","text":"Body 2."}]}',
        '{"turns":[{"speaker":"Ben","text":"Bye."}]}',
    ]
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.side_effect = [_mock_response(s) for s in seg_responses]
        transcript = run_transcript_stage(
            briefing="b", content="c",
            speakers=speakers, outline=outline, language=None,
            transcript_provider="anthropic",
            transcript_model="claude-sonnet-4",
            cost_meter=cost_meter,
        )
    assert isinstance(transcript, Transcript)
    assert len(transcript.turns) == 5
    assert mock.call_count == 3
    # Segment index annotation
    assert transcript.turns[0].segment_index == 0
    assert transcript.turns[2].segment_index == 1
    assert transcript.turns[4].segment_index == 2


def test_run_transcript_stage_records_cost_per_call(speakers, outline, cost_meter):
    one = '{"turns":[{"speaker":"Sophie","text":"x"}]}'
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.return_value = _mock_response(one)
        run_transcript_stage(
            briefing="b", content="c",
            speakers=speakers, outline=outline, language=None,
            transcript_provider="anthropic",
            transcript_model="claude-sonnet-4",
            cost_meter=cost_meter,
        )
    # All three calls record under the same "transcript" stage
    for call in mock.call_args_list:
        assert call.kwargs["stage"] == "transcript"
        assert call.kwargs["cost_meter"] is cost_meter


def test_run_transcript_stage_uses_cache_control_for_anthropic(speakers, outline, cost_meter):
    one = '{"turns":[{"speaker":"Sophie","text":"x"}]}'
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.return_value = _mock_response(one)
        run_transcript_stage(
            briefing="b", content="c",
            speakers=speakers, outline=outline, language=None,
            transcript_provider="anthropic",
            transcript_model="claude-sonnet-4",
            cost_meter=cost_meter,
        )
    # First call should have cache_control marker
    first_msgs = mock.call_args_list[0].kwargs["messages"]
    parts = first_msgs[0]["content"]
    assert isinstance(parts, list)
    assert parts[0].get("cache_control") == {"type": "ephemeral"}


def test_run_transcript_stage_rejects_unknown_speaker(speakers, outline, cost_meter):
    bad = '{"turns":[{"speaker":"Charlie","text":"hi"}]}'
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.return_value = _mock_response(bad)
        with pytest.raises(ValueError, match="unknown speaker"):
            run_transcript_stage(
                briefing="b", content="c",
                speakers=speakers, outline=outline, language=None,
                transcript_provider="anthropic",
                transcript_model="claude-sonnet-4",
                cost_meter=cost_meter,
            )


def test_run_transcript_stage_handles_code_fence(speakers, outline, cost_meter):
    fenced = '```json\n{"turns":[{"speaker":"Sophie","text":"hi"}]}\n```'
    with patch("gencast.pipeline.transcript.chat_completion") as mock:
        mock.return_value = _mock_response(fenced)
        transcript = run_transcript_stage(
            briefing="b", content="c",
            speakers=speakers, outline=outline, language=None,
            transcript_provider="anthropic",
            transcript_model="claude-sonnet-4",
            cost_meter=cost_meter,
        )
    assert transcript.turns[0].text == "hi"
