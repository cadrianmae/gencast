import pytest
from pydantic import ValidationError
from gencast.profiles.schemas import RoomProfile


def test_room_profile_defaults_match_v1_small_room():
    rp = RoomProfile(name="small-room")
    assert rp.arc_deg == 120.0
    assert rp.reverb_t60_s == 0.30
    assert rp.reverb_wet == 0.05
    assert rp.reverb_lpf_hz == 2000.0
    assert rp.reverb_damping == 0.55
    assert rp.predelay_ms == 20.0
    assert rp.ambience_db == -70.0
    assert rp.target_dbfs == -1.0


def test_room_profile_disable_ambience():
    rp = RoomProfile(name="silent", ambience_db=None)
    assert rp.ambience_db is None


def test_room_profile_extreme_t60():
    rp = RoomProfile(name="hall", reverb_t60_s=2.5, reverb_wet=0.20)
    assert rp.reverb_t60_s == 2.5


def test_room_profile_negative_arc_rejected():
    with pytest.raises(ValidationError):
        RoomProfile(name="bad", arc_deg=-10.0)


def test_room_profile_arc_over_180_rejected():
    with pytest.raises(ValidationError):
        RoomProfile(name="bad", arc_deg=200.0)
