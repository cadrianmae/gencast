"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import pytest

from gencast.cost import CostMeter


@pytest.fixture
def cost_meter():
    return CostMeter()


@pytest.fixture
def mock_llm_outline_response():
    """Build a mock LLMResponse-like object that returns a valid Outline JSON."""
    def _make(json_str: str = '{"segments":[{"name":"A","description":"d","size":"short"},{"name":"B","description":"d","size":"medium"},{"name":"C","description":"d","size":"long"},{"name":"D","description":"d","size":"medium"},{"name":"E","description":"d","size":"short"}]}'):
        resp = MagicMock()
        resp.content = json_str
        resp.tokens_in = 5000
        resp.tokens_out = 600
        resp.cache_reads_in = 0
        resp.cache_writes_in = 0
        resp.usd = 0.005
        return resp
    return _make


from gencast.notebook import Notebook, ResolvedNotebook
from gencast.pipeline import PodcastState
from gencast.pipeline.outline import Outline, OutlineSegment
from gencast.pipeline.transcript import Transcript, TranscriptTurn
from gencast.profiles.schemas import (
    EpisodeProfile, RoomProfile, Speaker, SpeakerProfile,
)


def _resolved_for_smoke():
    sp = SpeakerProfile(
        name="revision-duo", tts_provider="openai", tts_model="tts-1-hd",
        speakers=[
            Speaker(name="Sophie", voice_id="nova", backstory="b", personality="p"),
            Speaker(name="Ben", voice_id="echo", backstory="b", personality="p"),
        ],
    )
    ep = EpisodeProfile(name="exam-revision", default_briefing="b")
    rm = RoomProfile(name="small-room")
    nb = Notebook(title="Smoke", sources=["dummy.md"])
    return ResolvedNotebook(
        notebook=nb, speaker=sp, episode=ep, room=rm,
        briefing="b",
        outline_provider="anthropic", outline_model="claude-haiku-4.5",
        transcript_provider="anthropic", transcript_model="claude-sonnet-4",
        num_segments=2, basename="smoke",
    )


@pytest.fixture
def sample_state_with_outline():
    resolved = _resolved_for_smoke()
    state = PodcastState(notebook=resolved.notebook, resolved=resolved)
    state.outline = Outline(segments=[
        OutlineSegment(name="Intro", description="d", size="short"),
        OutlineSegment(name="Wrap", description="d", size="short"),
    ])
    return state


@pytest.fixture
def sample_state_with_transcript(sample_state_with_outline):
    state = sample_state_with_outline
    t1 = TranscriptTurn(speaker="Sophie", text="Hi.")
    t1.segment_index = 0
    t2 = TranscriptTurn(speaker="Ben", text="Bye.")
    t2.segment_index = 1
    state.transcript = Transcript(turns=[t1, t2])
    return state
