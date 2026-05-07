import pytest
from gencast.profiles.loader import load_profile

EXPECTED = ["educational-duo", "revision-duo", "solo-tutor", "interview-duo"]


@pytest.mark.parametrize("name", EXPECTED)
def test_bundled_speaker_profile_loads(name):
    sp = load_profile("speakers", name)
    assert sp.name == name
    assert sp.tts_provider in {"openai", "speaches"}
    assert 1 <= len(sp.speakers) <= 4


def test_solo_tutor_has_one_speaker():
    sp = load_profile("speakers", "solo-tutor")
    assert len(sp.speakers) == 1


def test_duos_have_two_speakers():
    for name in ["educational-duo", "revision-duo", "interview-duo"]:
        sp = load_profile("speakers", name)
        assert len(sp.speakers) == 2, f"{name} should have 2 speakers"
