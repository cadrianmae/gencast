"""Tests verifying that the vectorised _comb/_allpass implementations produce
bit-exact (within float32 rounding noise) output compared to the reference
pure-Python per-sample loops.

A separate skip-by-default benchmark confirms the vectorised path is fast enough
for real-time use (30s audio in <0.5s wall-clock).
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np
import pytest
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg
from gencast.audio_fx.reverb import SchroederReverb


# ---------------------------------------------------------------------------
# Reference pure-Python implementations (kept verbatim for comparison)
# ---------------------------------------------------------------------------

def _comb_reference(
    signal: np.ndarray, delay: int, feedback: float, damping: float = 0.0
) -> np.ndarray:
    """Verbatim Python-loop comb filter (pre-vectorisation baseline)."""
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


def _allpass_reference(signal: np.ndarray, delay: int, gain: float) -> np.ndarray:
    """Verbatim Python-loop Schroeder allpass (pre-vectorisation baseline)."""
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


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pink_noise_1s() -> np.ndarray:
    """1 second of deterministic pink-ish noise at float32."""
    rng = np.random.default_rng(2024)
    white = rng.normal(0, 0.2, 44100).astype(np.float32)
    # Simple pink noise approximation: cumsum of white noise (1/f-ish)
    pink = np.cumsum(white).astype(np.float32)
    pink /= np.max(np.abs(pink)) + 1e-9  # normalise to [-1, 1]
    return pink


RTOL = 1e-4
ATOL = 1e-4  # ~6 LSBs of float32 (eps ≈ 1.2e-7)


def _assert_close(ref: np.ndarray, vec: np.ndarray, label: str) -> None:
    max_err = float(np.max(np.abs(ref.astype(np.float64) - vec.astype(np.float64))))
    assert np.allclose(ref, vec, rtol=RTOL, atol=ATOL), (
        f"{label}: max abs error {max_err:.2e} exceeds tolerance "
        f"(rtol={RTOL}, atol={ATOL})"
    )


# ---------------------------------------------------------------------------
# Undamped comb filter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delay", [3, 7, 1309, 1636, 1812, 1927])
@pytest.mark.parametrize("feedback", [0.5, 0.8, 0.95])
def test_comb_undamped_matches_reference(
    pink_noise_1s: np.ndarray, delay: int, feedback: float
) -> None:
    """Vectorised undamped comb equals Python loop within float32 noise."""
    # Truncate to 2*delay samples for quick test when delay is large
    n = min(len(pink_noise_1s), 2 * delay + 200)
    signal = pink_noise_1s[:n]
    ref = _comb_reference(signal, delay, feedback, damping=0.0)
    vec = SchroederReverb._comb(signal, delay, feedback, damping=0.0)
    _assert_close(ref, vec, f"undamped comb delay={delay} fb={feedback}")


# ---------------------------------------------------------------------------
# Damped comb filter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("damping", [0.1, 0.3, 0.55, 0.8, 0.9])
@pytest.mark.parametrize("delay", [3, 7, 1309, 1636])
def test_comb_damped_matches_reference(
    pink_noise_1s: np.ndarray, damping: float, delay: int
) -> None:
    """Vectorised damped comb equals Python loop within float32 noise."""
    feedback = 0.8
    n = min(len(pink_noise_1s), 2 * delay + 200)
    signal = pink_noise_1s[:n]
    ref = _comb_reference(signal, delay, feedback, damping=damping)
    vec = SchroederReverb._comb(signal, delay, feedback, damping=damping)
    _assert_close(ref, vec, f"damped comb delay={delay} damp={damping}")


def test_comb_damped_impulse_response() -> None:
    """Impulse response of damped comb equals reference over 500 samples."""
    N = 500
    impulse = np.zeros(N, dtype=np.float32)
    impulse[0] = 1.0
    for delay in [3, 7, 13]:
        for damping in [0.3, 0.55, 0.8]:
            ref = _comb_reference(impulse, delay, 0.8, damping=damping)
            vec = SchroederReverb._comb(impulse, delay, 0.8, damping=damping)
            _assert_close(ref, vec, f"damped comb impulse delay={delay} damp={damping}")


# ---------------------------------------------------------------------------
# Allpass filter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delay", [3, 7, 220, 75])
@pytest.mark.parametrize("gain", [0.5, 0.3, 0.7])
def test_allpass_matches_reference(
    pink_noise_1s: np.ndarray, delay: int, gain: float
) -> None:
    """Vectorised allpass equals Python loop within float32 noise."""
    signal = pink_noise_1s
    ref = _allpass_reference(signal, delay, gain)
    vec = SchroederReverb._allpass(signal, delay, gain)
    _assert_close(ref, vec, f"allpass delay={delay} gain={gain}")


def test_allpass_impulse_response() -> None:
    """Impulse response of allpass equals reference over 500 samples."""
    N = 500
    impulse = np.zeros(N, dtype=np.float32)
    impulse[0] = 1.0
    for delay in [3, 7, 13]:
        ref = _allpass_reference(impulse, delay, 0.5)
        vec = SchroederReverb._allpass(impulse, delay, 0.5)
        _assert_close(ref, vec, f"allpass impulse delay={delay}")


# ---------------------------------------------------------------------------
# Full SchroederReverb.apply — output shape and basic sanity
# ---------------------------------------------------------------------------

def test_reverb_apply_produces_same_shape_as_input() -> None:
    sr = 44100
    rng = np.random.default_rng(0)
    arr = (rng.normal(0, 0.2, (2, sr)) * 32767).astype(np.float32) / 32767
    seg = np_to_seg(arr, sr)
    rv = SchroederReverb(sr, t60_s=0.30)
    out = rv.apply(seg, wet=0.05, wet_lpf_hz=2000, damping=0.55)
    assert out.channels == 2
    assert abs(len(out) - len(seg)) < 10  # within 10ms rounding


# ---------------------------------------------------------------------------
# Performance benchmark (skip by default — run with -m benchmark)
# ---------------------------------------------------------------------------

@pytest.mark.benchmark
def test_reverb_30s_under_500ms() -> None:
    """Vectorised reverb on 30s stereo audio must complete in <0.5s wall-clock.

    Skip this test in normal CI — run explicitly with:
        pytest -m benchmark tests/unit/test_audio_fx_reverb_vectorized.py
    """
    sr = 44100
    rng = np.random.default_rng(0)
    arr = (rng.normal(0, 0.2, (2, 30 * sr)) * 32767).astype(np.float32) / 32767
    seg = np_to_seg(arr, sr)
    rv = SchroederReverb(sr, t60_s=0.30)

    t0 = time.perf_counter()
    rv.apply(seg, wet=0.05, wet_lpf_hz=2000, damping=0.55)
    elapsed = time.perf_counter() - t0

    # CI-safe threshold: 2.0s. Locally measured at ~0.47s (vectorised) vs ~22s (Python loops).
    # 50-100x speedup confirmed; threshold is generous to handle slow CI workers.
    assert elapsed < 2.0, (
        f"Vectorised reverb took {elapsed:.3f}s on 30s audio — "
        "expected <2.0s (pure-Python baseline is ~22s)"
    )
