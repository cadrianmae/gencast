"""Tests for Avatar + Speaker pydantic schemas."""

import pytest
from pydantic import ValidationError

from gencast.profiles.schemas import Avatar, Speaker


def test_avatar_all_fields_optional():
    """All Avatar fields default to None."""
    a = Avatar()
    assert a.emoji is None
    assert a.ascii is None
    assert a.image is None
    assert a.color is None


def test_avatar_with_fields():
    """Avatar accepts emoji + color fields."""
    a = Avatar(emoji="🦊", color="#ff7847")
    assert a.emoji == "🦊"
    assert a.color == "#ff7847"


def test_speaker_required_fields():
    """Speaker requires name, voice_id, backstory, personality."""
    s = Speaker(name="Sophie", voice_id="nova", backstory="bg", personality="p")
    assert s.name == "Sophie"
    assert s.voice_id == "nova"
    assert s.avatar is None


def test_speaker_with_avatar():
    """Speaker can carry an Avatar via dict."""
    s = Speaker(
        name="Sophie", voice_id="nova", backstory="bg", personality="p",
        avatar={"emoji": "🦊"},
    )
    assert s.avatar.emoji == "🦊"


def test_speaker_missing_field_raises():
    """Missing required field raises ValidationError."""
    with pytest.raises(ValidationError):
        Speaker(name="Sophie", voice_id="nova", backstory="bg")  # personality missing


def test_speaker_per_speaker_tts_override():
    """Speaker can override tts_provider/model/config."""
    s = Speaker(
        name="Sophie", voice_id="nova", backstory="bg", personality="p",
        tts_provider="speaches", tts_model="kokoro",
        tts_config={"base_url": "http://localhost:8969"},
    )
    assert s.tts_provider == "speaches"
    assert s.tts_config["base_url"] == "http://localhost:8969"
