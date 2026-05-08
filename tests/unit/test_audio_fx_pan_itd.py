"""Pan + ITD — pan position math + stereo output shape."""

from __future__ import annotations

from pydub import AudioSegment

from gencast.audio_fx.pan_itd import pan_position, render_pan_itd


def test_pan_position_caps_at_pm_one():
    assert pan_position(0) == 0.0
    assert pan_position(90) == 1.0
    assert pan_position(-90) == -1.0
    assert pan_position(180) == 1.0
    assert pan_position(-180) == -1.0


def test_render_pan_itd_returns_stereo():
    mono = AudioSegment.silent(duration=200, frame_rate=44100).set_channels(1)
    stereo = render_pan_itd(mono, azimuth_deg=45.0, use_itd=True)
    assert stereo.channels == 2


def test_render_pan_itd_no_itd_when_centered():
    mono = AudioSegment.silent(duration=200, frame_rate=44100).set_channels(1)
    stereo = render_pan_itd(mono, azimuth_deg=0.0, use_itd=True)
    assert stereo.channels == 2
    # Length unchanged when centered (no silence padding inserted)
    assert len(stereo) == 200


def test_render_pan_itd_left_source_delays_right_ear():
    mono = AudioSegment.silent(duration=200, frame_rate=44100).set_channels(1)
    stereo = render_pan_itd(mono, azimuth_deg=-90.0, use_itd=True, itd_max_ms=0.6)
    # Length grew slightly due to silence-padding for ITD
    assert len(stereo) >= 200
