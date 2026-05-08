import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.distance import attenuate_for_distance


def _random_seg(sr=44100, n=4410):
    rng = np.random.default_rng(0)
    arr = rng.normal(0, 0.3, (2, n)).astype(np.float32)
    return np_to_seg(arr, sr)


def test_no_change_at_reference_distance():
    seg = _random_seg()
    out = attenuate_for_distance(seg, distance_m=0.85, ref_distance_m=0.85)
    pre, post = seg_to_np(seg), seg_to_np(out)
    assert np.allclose(pre, post, atol=1e-3)


def test_attenuates_at_double_distance():
    seg = _random_seg()
    out = attenuate_for_distance(seg, distance_m=1.70, ref_distance_m=0.85)
    pre_peak = np.max(np.abs(seg_to_np(seg)))
    post_peak = np.max(np.abs(seg_to_np(out)))
    # -6 dB ≈ ×0.5
    assert 0.4 < (post_peak / pre_peak) < 0.6
