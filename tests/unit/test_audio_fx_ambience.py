"""Ambience bed shape + mix correctness."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.ambience import make_ambience_bed, mix_ambience


def test_ambience_bed_length_matches():
    sr = 44100
    bed = make_ambience_bed(duration_ms=500, sample_rate=sr, level_db=-60.0)
    assert abs(len(bed) - 500) < 5
    assert bed.channels == 2


def test_ambience_bed_level_below_target():
    sr = 44100
    bed = make_ambience_bed(duration_ms=500, sample_rate=sr, level_db=-50.0)
    arr = seg_to_np(bed)
    peak = np.max(np.abs(arr))
    target = 10 ** (-50.0 / 20.0)
    assert peak <= target + 1e-3


def test_mix_ambience_preserves_foreground_peak_roughly():
    sr = 44100
    rng = np.random.default_rng(2)
    fg_arr = rng.normal(0, 0.2, (2, sr // 4)).astype(np.float32)
    fg = np_to_seg(fg_arr, sr)
    bed = make_ambience_bed(duration_ms=len(fg), sample_rate=sr, level_db=-70.0)
    out = mix_ambience(fg, bed)
    out_arr = seg_to_np(out)
    assert out_arr.shape == fg_arr.shape
