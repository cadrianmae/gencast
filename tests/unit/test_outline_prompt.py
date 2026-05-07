import pytest
from gencast.profiles.schemas import Speaker
from gencast.pipeline.outline import (
    Outline, OutlineSegment,
    render_outline_prompt,
)


def test_outline_segment_validation():
    s = OutlineSegment(name="Intro", description="welcome", size="short")
    assert s.size == "short"


def test_outline_segment_invalid_size_rejected():
    with pytest.raises(Exception):
        OutlineSegment(name="x", description="x", size="huge")


def test_outline_holds_segments():
    o = Outline(segments=[
        OutlineSegment(name="A", description="a", size="short"),
        OutlineSegment(name="B", description="b", size="medium"),
    ])
    assert len(o.segments) == 2


def _sample_speakers():
    return [
        Speaker(name="Sophie", voice_id="nova", backstory="bg1", personality="p1"),
        Speaker(name="Ben", voice_id="echo", backstory="bg2", personality="p2"),
    ]


def test_render_outline_prompt_basic():
    text = render_outline_prompt(
        briefing="A cool podcast",
        content="Source content here.",
        speakers=_sample_speakers(),
        num_segments=5,
        language=None,
    )
    assert "A cool podcast" in text
    assert "Source content here" in text
    assert "Sophie" in text
    assert "Ben" in text
    assert "5" in text


def test_render_outline_prompt_with_language():
    text = render_outline_prompt(
        briefing="b", content="c",
        speakers=_sample_speakers(),
        num_segments=3, language="Portuguese",
    )
    assert "Portuguese" in text


def test_render_outline_prompt_no_language_excludes_clause():
    text = render_outline_prompt(
        briefing="b", content="c",
        speakers=_sample_speakers(),
        num_segments=3, language=None,
    )
    assert "LANGUAGE INSTRUCTION" not in text.upper()
