"""Ambience bed (NC 20 colored noise) + mix. Lifted from scratch/immersion_test.py:249-318."""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np


def make_ambience_bed(
    duration_ms: int,
    sample_rate: int = 44100,
    level_db: float = -50.0,
    lpf_hz: float = 1500.0,
    fan_rumble_db: float = 4.0,
) -> AudioSegment:
    """Pink-noise base + LPF + optional 80Hz low-shelf for fan rumble. Stereo."""
    from scipy.signal import iirfilter, sosfilt

    n_samples = int(round(duration_ms * 0.001 * sample_rate))
    rng = np.random.default_rng(42)
    white = rng.normal(0.0, 1.0, n_samples).astype(np.float32)
    n_fft = 1
    while n_fft < n_samples:
        n_fft *= 2
    spectrum = np.fft.rfft(white, n=n_fft)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    shaping = np.where(freqs > 0, 1.0 / np.sqrt(freqs + 10.0), 1.0)
    shaping /= shaping.max()
    pink = np.fft.irfft(spectrum * shaping, n=n_fft)[:n_samples].astype(np.float32)

    sos = iirfilter(2, lpf_hz, btype="low", ftype="butter", fs=sample_rate, output="sos")
    pink = sosfilt(sos, pink).astype(np.float32)

    if fan_rumble_db > 0.0:
        shelf = iirfilter(2, 80, btype="low", ftype="butter", fs=sample_rate, output="sos")
        rumble = sosfilt(shelf, pink).astype(np.float32)
        boost = (10 ** (fan_rumble_db / 20.0)) - 1.0
        pink = (pink + boost * rumble).astype(np.float32)

    decorr_samples = int(round(0.0005 * sample_rate))
    pink_l = pink
    pink_r = np.concatenate([np.zeros(decorr_samples, dtype=np.float32), pink])[: len(pink_l)]
    stereo = np.stack([pink_l, pink_r])
    target_amp = 10 ** (level_db / 20.0)
    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo * (target_amp / peak)
    return np_to_seg(stereo, sample_rate=sample_rate)


def mix_ambience(foreground: AudioSegment, ambience: AudioSegment) -> AudioSegment:
    """Sum ambience under foreground, matching length."""
    f_arr = seg_to_np(foreground)
    a_arr = seg_to_np(ambience)
    n = f_arr.shape[1]
    if a_arr.shape[1] < n:
        reps = (n // a_arr.shape[1]) + 1
        a_arr = np.tile(a_arr, (1, reps))
    a_arr = a_arr[:, :n]
    out = f_arr + a_arr
    peak = np.max(np.abs(out))
    if peak > 0.99:
        out *= 0.99 / peak
    return np_to_seg(out, sample_rate=foreground.frame_rate)
