"""Tiny Schroeder reverb. Lifted from scratch/spatial_test.py:421-545.

4 parallel feedback comb filters → 2 series allpass filters. Feedback gain per
delay so all combs decay to the same T60.
"""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np


class SchroederReverb:
    """
    Tiny Schroeder reverb: 4 parallel feedback comb filters → 2 series allpass filters.

    Feedback gains derived from target T60 (decay-to-60dB time) per the standard
    Schroeder relation: T60 = -3·delay / log10(g) → g = 10^(-3·delay/T60).
    Vocal-booth target: T60 ≈ 0.2-0.3s (per Stanford CCRMA / Schroeder 1962).

    Mono in, stereo out (separate L/R taps).
    """

    DEFAULT_COMB_DELAYS_MS = (29.7, 37.1, 41.1, 43.7)
    ALLPASS_DELAYS_MS = (5.0, 1.7)
    ALLPASS_GAIN = 0.5
    DEFAULT_WET = 0.05
    DEFAULT_T60_S = 0.25

    def __init__(
        self,
        sample_rate: int = 44100,
        comb_delays_ms: tuple[float, ...] = DEFAULT_COMB_DELAYS_MS,
        t60_s: float = DEFAULT_T60_S,
    ):
        self.sr = sample_rate
        self.t60_s = t60_s
        self.comb_delays_ms = comb_delays_ms
        self.comb_delays = [int(d * sample_rate / 1000.0) for d in comb_delays_ms]
        self.allpass_delays = [int(d * sample_rate / 1000.0) for d in self.ALLPASS_DELAYS_MS]
        self.comb_feedback = tuple(
            10 ** (-3 * (d_ms / 1000.0) / t60_s) for d_ms in comb_delays_ms
        )

    @staticmethod
    def _comb(signal: np.ndarray, delay: int, feedback: float, damping: float = 0.0) -> np.ndarray:
        """
        Feedback comb filter with optional one-pole lowpass in the feedback path.
        damping=0.0 → no high-freq damping (flat reverb decay).
        damping in [0.0, 0.95] → high frequencies decay faster than lows.
        Real rooms typically need damping ~0.4-0.6 for natural sound.
        """
        out = np.zeros_like(signal)
        buf = np.zeros(delay, dtype=np.float32)
        idx = 0
        lpf_state = np.float32(0.0)
        a = np.float32(max(0.0, min(0.95, damping)))
        if a == 0.0:
            for i in range(len(signal)):
                delayed = buf[idx]
                new = signal[i] + feedback * delayed
                buf[idx] = new
                out[i] = delayed
                idx = (idx + 1) % delay
        else:
            for i in range(len(signal)):
                delayed = buf[idx]
                lpf_state = a * lpf_state + (1.0 - a) * delayed
                new = signal[i] + feedback * lpf_state
                buf[idx] = new
                out[i] = delayed
                idx = (idx + 1) % delay
        return out

    @staticmethod
    def _allpass(signal: np.ndarray, delay: int, gain: float) -> np.ndarray:
        out = np.zeros_like(signal)
        buf = np.zeros(delay, dtype=np.float32)
        idx = 0
        for i in range(len(signal)):
            delayed = buf[idx]
            new = signal[i] + gain * delayed
            buf[idx] = new
            out[i] = -gain * new + delayed
            idx = (idx + 1) % delay
        return out

    def apply(
        self,
        seg: AudioSegment,
        wet: float = DEFAULT_WET,
        wet_lpf_hz: float | None = None,
        damping: float = 0.0,
    ) -> AudioSegment:
        """
        wet_lpf_hz: if set, low-pass the wet (reverb) signal at this cutoff before
        mixing. Simulates absorption by soft surfaces (padded room = lower cutoff).
        """
        if seg.frame_rate != self.sr:
            seg = seg.set_frame_rate(self.sr)
        signal = seg_to_np(seg)  # (channels, N)
        if signal.shape[0] == 1:
            signal = np.tile(signal, (2, 1))

        out = np.zeros_like(signal)
        for ch in (0, 1):
            x = signal[ch]
            # Sum of parallel combs (with optional feedback-path damping)
            comb_sum = np.zeros_like(x)
            for d, fb in zip(self.comb_delays, self.comb_feedback):
                comb_sum += self._comb(x, d, fb, damping=damping)
            comb_sum /= len(self.comb_delays)
            # Series allpass
            y = comb_sum
            for d in self.allpass_delays:
                y = self._allpass(y, d, self.ALLPASS_GAIN)
            out[ch] = y

        # Optional LPF on the wet signal — emulates absorptive surfaces (padded room)
        if wet_lpf_hz is not None:
            from scipy.signal import iirfilter, sosfilt
            sos = iirfilter(2, wet_lpf_hz, btype="low", ftype="butter",
                            fs=self.sr, output="sos")
            for ch in range(out.shape[0]):
                out[ch] = sosfilt(sos, out[ch])

        # Wet/dry mix
        mixed = (1.0 - wet) * signal + wet * out
        peak = np.max(np.abs(mixed))
        if peak > 0.99:
            mixed *= 0.99 / peak

        return np_to_seg(mixed, sample_rate=self.sr)
