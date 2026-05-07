from unittest.mock import patch
import pytest
from gencast.notebook import Notebook, load_notebook
from gencast.pipeline import PodcastState, run_through_outline


@pytest.fixture
def sample_notebook(tmp_path):
    src = tmp_path / "lecture.md"
    src.write_text("Photosynthesis is the process by which plants make food from sunlight.")
    nb_path = tmp_path / "nb.yaml"
    nb_path.write_text(
        f"title: Test\n"
        f"sources: [{src}]\n"
    )
    return load_notebook(nb_path)


def test_run_through_outline_full_path(sample_notebook, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        state = run_through_outline(sample_notebook)

    assert isinstance(state, PodcastState)
    assert state.source_text != ""
    assert "Photosynthesis" in state.source_text
    assert state.source_tokens_original > 0
    assert state.outline is not None
    assert len(state.outline.segments) >= 3


def test_run_through_outline_passes_cost_meter(sample_notebook, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        state = run_through_outline(sample_notebook)
    # chat_completion is mocked, so cost recording inside it is bypassed.
    # Verify the orchestrator wired the cost_meter through correctly.
    assert mock.called
    call_kwargs = mock.call_args.kwargs
    assert call_kwargs["cost_meter"] is state.cost
    assert call_kwargs["stage"] == "outline"
