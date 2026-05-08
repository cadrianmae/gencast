"""Amplitude pan + ITD. Lifted from scratch/no_hrtf_test.py:62-96."""

from __future__ import annotations

from pydub import AudioSegment


def pan_position(azimuth_deg: float) -> float:
    """Map azimuth (deg) to pydub-style pan position. ±90° → ±1.0, capped."""
    return max(-1.0, min(1.0, azimuth_deg / 90.0))


def render_pan_itd(
    mono: AudioSegment,
    azimuth_deg: float,
    *,
    use_itd: bool = True,
    itd_max_ms: float = 0.6,
) -> AudioSegment:
    """Convert mono → stereo with amplitude pan + (optional) ITD."""
    pos = pan_position(azimuth_deg)
    seg = mono.set_channels(2) if mono.channels < 2 else mono
    seg = seg.pan(pos)
    if not use_itd:
        return seg
    itd_ms = abs(pos) * itd_max_ms
    if itd_ms < 0.01:
        return seg
    silence = AudioSegment.silent(duration=int(itd_ms), frame_rate=seg.frame_rate)
    channels = seg.split_to_mono()
    if len(channels) != 2:
        return seg
    left, right = channels
    if pos < 0:  # left source: delay right ear
        right = silence + right
        left = left + silence
    else:
        left = silence + left
        right = right + silence
    return AudioSegment.from_mono_audiosegments(left, right)
