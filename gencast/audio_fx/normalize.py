"""Peak normalize. Lifted from scratch/spatial_test.py:551-561."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np


def peak_normalize(seg: AudioSegment, target_dbfs: float = -1.0) -> AudioSegment:
    """Scale so the absolute peak hits target_dbfs (dBFS, ≤ 0)."""
    arr = seg_to_np(seg)
    peak = float(np.max(np.abs(arr)))
    if peak < 1e-6:
        return seg
    target_linear = 10 ** (target_dbfs / 20.0)
    arr = arr * (target_linear / peak)
    return np_to_seg(arr, sample_rate=seg.frame_rate)
