"""Per-bundled-room digest regression test.

Inputs: 1s of seeded pink noise through `apply_room` for each bundled room
preset. Outputs: peak (dBFS), RMS (dBFS), length_ms. Drift in any of these
indicates unintended audio FX change.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from gencast.audio_fx import render_clip_with_room, speaker_seat_distance
from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.reverb import SchroederReverb
from gencast.profiles.loader import load_profile
from gencast.profiles.schemas import RoomProfile

REFERENCE = Path(__file__).parent.parent / "fixtures" / "audio_reference" / "silence_1s.json"
TARGET_SR = 44100


def _seeded_pink_noise(duration_ms: int = 1000, seed: int = 42):
    rng = np.random.default_rng(seed)
    n = int(duration_ms / 1000 * TARGET_SR)
    arr = rng.normal(0, 0.2, (1, n)).astype(np.float32)
    return np_to_seg(arr, TARGET_SR)


def _digest(seg) -> dict[str, float]:
    arr = seg_to_np(seg)
    peak = float(np.max(np.abs(arr)))
    rms = float(np.sqrt(np.mean(arr ** 2)))
    return {
        "peak_dbfs": 20 * float(np.log10(peak + 1e-12)),
        "rms_dbfs": 20 * float(np.log10(rms + 1e-12)),
        "length_ms": float(len(seg)),
    }


def _bundled_rooms() -> list[str]:
    return [
        "small-room", "dry", "large-room", "vocal-booth",
        "wide", "narrow", "ambient", "silent",
    ]


@pytest.mark.parametrize("room_name", _bundled_rooms())
def test_room_digest_matches_reference(room_name):
    if not REFERENCE.exists():
        pytest.skip(f"Reference file {REFERENCE} not present — run scripts/regenerate_audio_reference.py")
    reference = json.loads(REFERENCE.read_text())
    if room_name not in reference:
        pytest.skip(f"Reference has no entry for {room_name}")
    expected = reference[room_name]

    room: RoomProfile = load_profile("rooms", room_name)
    mono = _seeded_pink_noise(1000)
    reverb = SchroederReverb(sample_rate=TARGET_SR, t60_s=room.reverb_t60_s)
    distance = speaker_seat_distance(0.0, room.table_radius_m)
    out = render_clip_with_room(
        mono, azimuth_deg=0.0, distance_m=distance,
        room=room, reverb=reverb, target_sr=TARGET_SR,
    )
    actual = _digest(out)

    for k in ("peak_dbfs", "rms_dbfs"):
        assert abs(actual[k] - expected[k]) < 0.5, (
            f"{room_name}.{k}: actual={actual[k]:.2f}, expected={expected[k]:.2f}"
        )
    assert abs(actual["length_ms"] - expected["length_ms"]) < 50, (
        f"{room_name}.length_ms: actual={actual['length_ms']}, expected={expected['length_ms']}"
    )
