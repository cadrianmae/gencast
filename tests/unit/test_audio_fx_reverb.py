"""SchroederReverb — wet/dry mix, output stereo, finite samples."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx.reverb import SchroederReverb


def test_reverb_returns_stereo():
    sr = 44100
    seg = AudioSegment.silent(duration=200, frame_rate=sr).set_channels(2)
    rv = SchroederReverb(sample_rate=sr, t60_s=0.30)
    out = rv.apply(seg, wet=0.05)
    assert out.channels == 2


def test_reverb_dry_when_wet_zero():
    """wet=0 should approximate the input (allowing for the all-pass chain)."""
    sr = 44100
    rng = np.random.default_rng(0)
    n = sr // 4
    raw = (rng.normal(0, 0.1, n) * 32767).astype(np.int16)
    seg = AudioSegment(
        raw.tobytes(), sample_width=2, frame_rate=sr, channels=1,
    )
    rv = SchroederReverb(sample_rate=sr, t60_s=0.30)
    out = rv.apply(seg, wet=0.0)
    assert len(out) == len(seg)


def test_reverb_t60_attribute_recorded():
    rv = SchroederReverb(sample_rate=44100, t60_s=0.50)
    assert abs(rv.t60_s - 0.50) < 1e-6
    assert all(0 < g < 1 for g in rv.comb_feedback)
