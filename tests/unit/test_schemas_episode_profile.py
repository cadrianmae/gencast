import pytest
from pydantic import ValidationError
from gencast.profiles.schemas import EpisodeProfile


def test_episode_profile_minimum():
    ep = EpisodeProfile(name="basic", default_briefing="A briefing.")
    assert ep.num_segments == 6
    assert ep.outline_provider == "anthropic"
    assert ep.transcript_model == "claude-sonnet-4-5"
    assert ep.segment_size_default == "medium"
    assert ep.language is None


def test_episode_profile_full():
    ep = EpisodeProfile(
        name="custom",
        description="A custom episode",
        speaker_profile="revision-duo",
        default_briefing="Revise everything.",
        num_segments=8,
        segment_size_default="long",
        outline_provider="openai",
        outline_model="gpt-4o-mini",
        transcript_provider="anthropic",
        transcript_model="claude-sonnet-4-5",
        language="en",
    )
    assert ep.num_segments == 8
    assert ep.speaker_profile == "revision-duo"


def test_episode_profile_segments_too_few():
    with pytest.raises(ValidationError, match="3-10"):
        EpisodeProfile(name="x", default_briefing="b", num_segments=2)


def test_episode_profile_segments_too_many():
    with pytest.raises(ValidationError, match="3-10"):
        EpisodeProfile(name="x", default_briefing="b", num_segments=11)


def test_episode_profile_segment_size_invalid():
    with pytest.raises(ValidationError):
        EpisodeProfile(name="x", default_briefing="b", segment_size_default="xl")


def test_episode_profile_summarize_falls_back():
    ep = EpisodeProfile(name="x", default_briefing="b")
    assert ep.summarize_provider is None
    assert ep.summarize_model is None
