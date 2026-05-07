from unittest.mock import patch

import pytest

from gencast.pipeline.outline import Outline, run_outline_stage
from gencast.profiles.schemas import Speaker


@pytest.fixture
def speakers():
    return [
        Speaker(name="Sophie", voice_id="nova", backstory="bg", personality="p"),
        Speaker(name="Ben", voice_id="echo", backstory="bg", personality="p"),
    ]


def test_run_outline_stage_happy_path(speakers, cost_meter, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        outline = run_outline_stage(
            briefing="b", content="c",
            speakers=speakers, num_segments=5, language=None,
            outline_provider="anthropic", outline_model="claude-haiku-4.5",
            cost_meter=cost_meter,
        )
    assert isinstance(outline, Outline)
    assert len(outline.segments) == 5


def test_run_outline_stage_records_cost(speakers, cost_meter, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        run_outline_stage(
            briefing="b", content="c",
            speakers=speakers, num_segments=5, language=None,
            outline_provider="anthropic", outline_model="claude-haiku-4.5",
            cost_meter=cost_meter,
        )
    call_kwargs = mock.call_args.kwargs
    assert call_kwargs["cost_meter"] is cost_meter
    assert call_kwargs["stage"] == "outline"


def test_run_outline_stage_handles_json_with_code_fence(speakers, cost_meter, mock_llm_outline_response):
    """Some models emit ```json ... ``` even when asked not to. Strip it."""
    fenced = '```json\n{"segments":[{"name":"X","description":"d","size":"short"}]}\n```'
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response(fenced)
        outline = run_outline_stage(
            briefing="b", content="c",
            speakers=speakers, num_segments=1, language=None,
            outline_provider="anthropic", outline_model="claude-haiku-4.5",
            cost_meter=cost_meter,
        )
    assert outline.segments[0].name == "X"


def test_run_outline_stage_invalid_json_raises(speakers, cost_meter, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response("not json")
        with pytest.raises(ValueError, match="JSON"):
            run_outline_stage(
                briefing="b", content="c",
                speakers=speakers, num_segments=1, language=None,
                outline_provider="anthropic", outline_model="claude-haiku-4.5",
                cost_meter=cost_meter,
            )
