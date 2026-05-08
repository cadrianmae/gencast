"""Audio FX orchestrator — applies a RoomProfile to clips and the combined mix."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from pydub import AudioSegment

from gencast.audio_fx._npbridge import np_to_seg, seg_to_np
from gencast.audio_fx.ambience import make_ambience_bed, mix_ambience
from gencast.audio_fx.distance import attenuate_for_distance
from gencast.audio_fx.normalize import peak_normalize
from gencast.audio_fx.pan_itd import render_pan_itd
from gencast.audio_fx.reverb import SchroederReverb

if TYPE_CHECKING:
    from gencast.profiles.schemas import RoomProfile


# Listener at room centre. Mirrors scratch/immersion_test.py.
_LISTENER_POS = (0.0, 0.0, 1.2)


def front_arc_azimuths(n_speakers: int, arc_deg: float = 120.0) -> list[float]:
    """Spread n speakers across a front arc; outer speakers at ±arc/2.

    n=1 → [0]
    n=2 → [-arc/2, +arc/2]
    n=3+ → outer at ±arc/2, evenly spaced inside.
    """
    if n_speakers <= 0:
        return []
    if n_speakers == 1:
        return [0.0]
    if n_speakers == 2:
        return [-arc_deg / 2, arc_deg / 2]
    step = arc_deg / (n_speakers - 1)
    return [-arc_deg / 2 + i * step for i in range(n_speakers)]


def speaker_seat_distance(
    azimuth_deg: float, table_radius_m: float,
) -> float:
    """Distance from listener to the seat at this azimuth on the round table."""
    sx = _LISTENER_POS[0] + table_radius_m * math.sin(math.radians(azimuth_deg))
    sy = _LISTENER_POS[1] + table_radius_m * math.cos(math.radians(azimuth_deg))
    sz = 1.2  # speaker mouth height
    return math.sqrt(
        (sx - _LISTENER_POS[0]) ** 2
        + (sy - _LISTENER_POS[1]) ** 2
        + (sz - _LISTENER_POS[2]) ** 2
    )


def _apply_predelay(
    direct: AudioSegment, mixed: AudioSegment, predelay_ms: float, target_sr: int,
) -> AudioSegment:
    """Replace the first `predelay_ms` of `mixed` with the dry signal."""
    if predelay_ms <= 0:
        return mixed
    pre_n = int(round(predelay_ms * 0.001 * target_sr))
    if pre_n <= 0:
        return mixed
    mixed_arr = seg_to_np(mixed)
    direct_arr = seg_to_np(direct)
    if mixed_arr.shape[1] < pre_n or direct_arr.shape[1] < pre_n:
        return mixed
    blended = mixed_arr.copy()
    blended[:, :pre_n] = direct_arr[:, :pre_n]
    return np_to_seg(blended, sample_rate=target_sr)


def render_clip_with_room(
    mono: AudioSegment,
    *,
    azimuth_deg: float,
    distance_m: float,
    room: "RoomProfile",
    reverb: SchroederReverb,
    target_sr: int,
) -> AudioSegment:
    """Apply the per-clip locked v1 pipeline to one sentence."""
    if mono.frame_rate != target_sr:
        mono = mono.set_frame_rate(target_sr)
    if mono.channels != 1:
        mono = mono.set_channels(1)

    direct = render_pan_itd(mono, azimuth_deg, use_itd=True, itd_max_ms=room.itd_max_ms)

    if room.reverb_wet > 0.0:
        wet = reverb.apply(
            direct,
            wet=room.reverb_wet,
            wet_lpf_hz=room.reverb_lpf_hz,
            damping=room.reverb_damping,
        )
        seg = _apply_predelay(direct, wet, room.predelay_ms, target_sr)
    else:
        seg = direct

    seg = attenuate_for_distance(seg, distance_m, ref_distance_m=room.table_radius_m)
    return seg
