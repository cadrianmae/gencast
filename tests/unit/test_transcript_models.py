"""Pydantic model tests for Transcript / TranscriptTurn."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gencast.pipeline.transcript import Transcript, TranscriptTurn


def test_turn_minimal():
    t = TranscriptTurn(speaker="Sophie", text="Hello world.")
    assert t.speaker == "Sophie"
    assert t.text == "Hello world."
    assert t.segment_index is None  # set by stage executor, not by parser


def test_turn_rejects_empty_text():
    with pytest.raises(ValidationError):
        TranscriptTurn(speaker="Sophie", text="")


def test_turn_rejects_empty_speaker():
    with pytest.raises(ValidationError):
        TranscriptTurn(speaker="", text="Hi.")


def test_transcript_minimal():
    t = Transcript(turns=[
        TranscriptTurn(speaker="Sophie", text="Hi."),
        TranscriptTurn(speaker="Ben", text="Hello."),
    ])
    assert len(t.turns) == 2


def test_transcript_rejects_empty():
    with pytest.raises(ValidationError):
        Transcript(turns=[])
