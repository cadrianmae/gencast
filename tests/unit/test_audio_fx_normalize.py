import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.normalize import peak_normalize


def test_peak_normalize_to_minus_one_dbfs():
    sr = 44100
    rng = np.random.default_rng(1)
    arr = rng.normal(0, 0.05, (2, sr // 4)).astype(np.float32)  # very low peak
    seg = np_to_seg(arr, sr)
    out = peak_normalize(seg, target_dbfs=-1.0)
    out_peak = np.max(np.abs(seg_to_np(out)))
    target = 10 ** (-1.0 / 20.0)
    assert abs(out_peak - target) < 0.02
