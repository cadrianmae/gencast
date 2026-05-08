"""Inverse-square distance attenuation. Lifted from scratch/immersion_test.py:185-198."""

from __future__ import annotations

import math

from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np


def attenuate_for_distance(
    seg: AudioSegment, distance_m: float, ref_distance_m: float = 0.85,
) -> AudioSegment:
    """-6 dB per doubling of distance, relative to reference radius."""
    if distance_m <= 0 or ref_distance_m <= 0:
        return seg
    db = 20.0 * math.log10(ref_distance_m / distance_m)
    if abs(db) < 0.01:
        return seg
    arr = seg_to_np(seg)
    arr = arr * (10 ** (db / 20.0))
    return np_to_seg(arr, sample_rate=seg.frame_rate)
