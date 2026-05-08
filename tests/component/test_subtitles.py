"""SRT building from clip timing."""

from __future__ import annotations

from pydub import AudioSegment

from gencast.pipeline.audio import AudioClip
from gencast.pipeline.subtitles import SrtEntry, build_native_srt, srt_format


def _clip(start, end, speaker, text):
    seg = AudioSegment.silent(duration=end - start, frame_rate=44100).set_channels(2)
    return AudioClip(
        start_ms=start, end_ms=end,
        speaker_index=0, speaker_name=speaker,
        sentence_text=text, segment_index=0, audio=seg,
    )


def test_build_native_srt_one_entry_per_clip():
    clips = [
        _clip(0, 1500, "Sophie", "Hello there."),
        _clip(1500, 3500, "Ben", "How are you?"),
    ]
    entries = build_native_srt(clips, include_speaker=True)
    assert len(entries) == 2
    assert entries[0].start_ms == 0
    assert entries[0].end_ms == 1500
    assert entries[0].text == "[Sophie] Hello there."
    assert entries[1].text == "[Ben] How are you?"


def test_build_native_srt_no_speaker_label():
    clips = [_clip(0, 1500, "Sophie", "Hi.")]
    entries = build_native_srt(clips, include_speaker=False)
    assert entries[0].text == "Hi."


def test_srt_format_one_entry():
    e = SrtEntry(index=1, start_ms=0, end_ms=1234, text="Hello.")
    out = srt_format([e])
    expected = (
        "1\n"
        "00:00:00,000 --> 00:00:01,234\n"
        "Hello.\n"
        "\n"
    )
    assert out == expected


def test_srt_format_multiple_entries():
    es = [
        SrtEntry(index=1, start_ms=0, end_ms=1500, text="One."),
        SrtEntry(index=2, start_ms=1500, end_ms=3500, text="Two."),
    ]
    out = srt_format(es)
    assert "1\n00:00:00,000 --> 00:00:01,500\nOne." in out
    assert "2\n00:00:01,500 --> 00:00:03,500\nTwo." in out
