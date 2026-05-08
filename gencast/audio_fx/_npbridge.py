"""Audio-NumPy bridge: Convert between AudioSegment and NumPy arrays."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment


def seg_to_np(seg: AudioSegment) -> np.ndarray:
    """AudioSegment → float32 ndarray of shape (channels, samples), range [-1, 1]."""
    samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
    if seg.channels == 2:
        samples = samples.reshape(-1, 2).T  # (2, N)
    else:
        samples = samples.reshape(1, -1)
    # Normalize to [-1, 1] from int16
    samples = samples / float(2 ** (8 * seg.sample_width - 1))
    return samples


def np_to_seg(arr: np.ndarray, sample_rate: int = 44100) -> AudioSegment:
    """float32 (channels, samples) ndarray → stereo AudioSegment."""
    if arr.ndim == 1:
        arr = np.stack([arr, arr])
    # Clip + scale to int16
    arr = np.clip(arr, -1.0, 1.0)
    arr = (arr * 32767.0).astype(np.int16)
    interleaved = arr.T.flatten().tobytes()
    return AudioSegment(
        data=interleaved,
        sample_width=2,
        frame_rate=sample_rate,
        channels=2,
    )
