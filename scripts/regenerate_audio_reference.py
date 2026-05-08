"""Regenerate tests/fixtures/audio_reference/silence_1s.json from current code.

Run after intentional changes to audio_fx (e.g., new reverb tuning). Commit
the updated JSON alongside the change so the regression test reflects the new
intended baseline.

Usage: ./venv/bin/python scripts/regenerate_audio_reference.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.unit.test_audio_reference_regression import (  # type: ignore
    _bundled_rooms, _digest, _seeded_pink_noise, REFERENCE, TARGET_SR,
)
from gencast.audio_fx import render_clip_with_room, speaker_seat_distance
from gencast.audio_fx.reverb import SchroederReverb
from gencast.profiles.loader import load_profile


def main() -> int:
    reference: dict[str, dict] = {}
    mono = _seeded_pink_noise(1000)
    for room_name in _bundled_rooms():
        room = load_profile("rooms", room_name)
        reverb = SchroederReverb(sample_rate=TARGET_SR, t60_s=room.reverb_t60_s)
        distance = speaker_seat_distance(0.0, room.table_radius_m)
        out = render_clip_with_room(
            mono, azimuth_deg=0.0, distance_m=distance,
            room=room, reverb=reverb, target_sr=TARGET_SR,
        )
        reference[room_name] = _digest(out)
        print(f"  {room_name}: {reference[room_name]}")
    REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE.write_text(json.dumps(reference, indent=2, sort_keys=True))
    print(f"Wrote {REFERENCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
