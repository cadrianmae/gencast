import pytest
from pathlib import Path
from pydantic import ValidationError
from gencast.notebook import Notebook, NotebookOutput, NotebookOverrides


def test_notebook_minimum():
    nb = Notebook(title="t", sources=["a.md"])
    assert nb.speaker_profile == "educational-duo"
    assert nb.episode_profile == "concept-explainer"
    assert nb.room_profile == "small-room"
    assert nb.output.formats == ["m4a"]
    assert nb.output.dir == Path("./out")


def test_notebook_full():
    nb = Notebook(
        title="t",
        description="desc",
        tags=["a", "b"],
        sources=["x.md", "y.md"],
        speaker_profile="revision-duo",
        episode_profile="exam-revision",
        room_profile="vocal-booth",
        output={"dir": "/tmp/out", "basename": "ep1", "formats": ["m4a", "mp3"]},
        overrides={
            "outline_model": "claude-haiku-4.5",
            "transcript_model": "claude-sonnet-4",
            "briefing_suffix": "Focus on X.",
        },
    )
    assert nb.output.formats == ["m4a", "mp3"]
    assert nb.overrides.briefing_suffix == "Focus on X."


def test_notebook_no_sources_rejected():
    with pytest.raises(ValidationError, match="sources"):
        Notebook(title="t", sources=[])


def test_notebook_invalid_format_rejected():
    with pytest.raises(ValidationError):
        Notebook(title="t", sources=["a.md"], output={"formats": ["wav"]})


def test_notebook_overrides_default_empty():
    nb = Notebook(title="t", sources=["a.md"])
    assert nb.overrides.outline_model is None
    assert nb.overrides.briefing_suffix is None


def test_notebook_strict_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Notebook(title="t", sources=["a.md"], unknown_field=123)
