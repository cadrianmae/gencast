import pytest
from pydantic import ValidationError
from gencast.profiles.schemas import SpeakerProfile, Speaker


def make_speaker(name: str, voice_id: str) -> dict:
    return {
        "name": name,
        "voice_id": voice_id,
        "backstory": "background",
        "personality": "personality",
    }


def test_speaker_profile_minimum():
    sp = SpeakerProfile(
        name="solo",
        tts_provider="openai",
        tts_model="tts-1-hd",
        speakers=[make_speaker("Sophie", "nova")],
    )
    assert len(sp.speakers) == 1


def test_speaker_profile_two_speakers():
    sp = SpeakerProfile(
        name="duo",
        tts_provider="openai",
        tts_model="tts-1-hd",
        speakers=[
            make_speaker("Sophie", "nova"),
            make_speaker("Ben", "echo"),
        ],
    )
    assert len(sp.speakers) == 2


def test_speaker_profile_zero_speakers_rejected():
    with pytest.raises(ValidationError, match="1-4"):
        SpeakerProfile(name="empty", tts_provider="openai", tts_model="tts-1-hd", speakers=[])


def test_speaker_profile_five_speakers_rejected():
    with pytest.raises(ValidationError, match="1-4"):
        SpeakerProfile(
            name="big",
            tts_provider="openai",
            tts_model="tts-1-hd",
            speakers=[make_speaker(f"S{i}", f"v{i}") for i in range(5)],
        )


def test_speaker_profile_duplicate_names_rejected():
    with pytest.raises(ValidationError, match="unique"):
        SpeakerProfile(
            name="dup",
            tts_provider="openai",
            tts_model="tts-1-hd",
            speakers=[make_speaker("Same", "nova"), make_speaker("Same", "echo")],
        )


def test_speaker_profile_duplicate_voices_rejected():
    with pytest.raises(ValidationError, match="unique"):
        SpeakerProfile(
            name="dup",
            tts_provider="openai",
            tts_model="tts-1-hd",
            speakers=[make_speaker("A", "nova"), make_speaker("B", "nova")],
        )
