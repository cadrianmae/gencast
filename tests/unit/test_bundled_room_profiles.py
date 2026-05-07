import pytest
from gencast.profiles.loader import load_profile

EXPECTED = [
    "small-room", "dry", "large-room", "vocal-booth",
    "wide", "narrow", "ambient", "silent",
]


@pytest.mark.parametrize("name", EXPECTED)
def test_bundled_room_profile_loads(name):
    rp = load_profile("rooms", name)
    assert rp.name == name


def test_dry_disables_reverb():
    rp = load_profile("rooms", "dry")
    assert rp.reverb_wet == 0.0
    assert rp.ambience_db is None


def test_silent_disables_ambience():
    rp = load_profile("rooms", "silent")
    assert rp.ambience_db is None


def test_small_room_matches_v1_defaults():
    rp = load_profile("rooms", "small-room")
    assert rp.reverb_t60_s == 0.30
    assert rp.reverb_wet == 0.05
    assert rp.reverb_lpf_hz == 2000.0


def test_vocal_booth_short_decay():
    rp = load_profile("rooms", "vocal-booth")
    assert rp.reverb_t60_s == 0.20
    assert rp.reverb_lpf_hz == 1500.0


def test_large_room_longer_decay():
    rp = load_profile("rooms", "large-room")
    assert rp.reverb_t60_s == 0.50


def test_wide_arc():
    rp = load_profile("rooms", "wide")
    assert rp.arc_deg == 160.0


def test_narrow_arc():
    rp = load_profile("rooms", "narrow")
    assert rp.arc_deg == 80.0


def test_ambient_audible_bed():
    rp = load_profile("rooms", "ambient")
    assert rp.ambience_db == -50.0
