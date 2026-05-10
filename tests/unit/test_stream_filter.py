"""Test the generic JsonObjectStreamFilter + outline_segment_emitter.

Transcript turn behaviour is covered by tests/unit/test_turn_stream_filter.py
which routes through the same primitive via the back-compat shim.
"""
from __future__ import annotations

from gencast.pipeline.stream_filter import (
    JsonObjectStreamFilter,
    outline_segment_emitter,
    transcript_turn_emitter,
)


def _feed(chunks: list[str], emitter):
    out: list[str] = []
    f = JsonObjectStreamFilter(emitter(out.append))
    for c in chunks:
        f.feed(c)
    return out


def test_outline_emits_one_line_per_segment():
    chunks = ['{"segments": [{"name": "A", "description": "first"}, ',
              '{"name": "B", "description": "second"}]}']
    assert _feed(chunks, outline_segment_emitter) == [
        "A: first\n",
        "B: second\n",
    ]


def test_outline_skips_objects_without_required_fields():
    chunks = ['{"segments": [{"name": "A", "description": "x"}, {"foo": "bar"}]}']
    assert _feed(chunks, outline_segment_emitter) == ["A: x\n"]


def test_outline_chunk_split_mid_segment_waits_for_close():
    f_out: list[str] = []
    f = JsonObjectStreamFilter(outline_segment_emitter(f_out.append))
    f.feed('{"segments": [{"name": "A", "description": "incomplete')
    assert f_out == []
    f.feed(' text"}, {"name": "B", "description": "done"}]}')
    assert f_out == ["A: incomplete text\n", "B: done\n"]


def test_outline_collapses_multiline_descriptions():
    chunks = [r'{"segments": [{"name": "A", "description": "line1\nline2\n  line3"}]}']
    assert _feed(chunks, outline_segment_emitter) == ["A: line1 line2 line3\n"]


def test_transcript_emitter_skips_segment_shape():
    """Transcript emitter should ignore objects that don't have speaker+text."""
    chunks = ['{"segments": [{"name": "A", "description": "x"}]}']
    assert _feed(chunks, transcript_turn_emitter) == []


def test_outline_emitter_skips_turn_shape():
    """Outline emitter should ignore objects that don't have name+description."""
    chunks = ['{"turns": [{"speaker": "A", "text": "x"}]}']
    assert _feed(chunks, outline_segment_emitter) == []


def test_invalid_json_object_silently_skipped():
    """A `}` inside a string shouldn't break the scanner."""
    chunks = [r'{"segments": [{"name": "A", "description": "has } in it"}]}']
    out = _feed(chunks, outline_segment_emitter)
    assert out == ["A: has } in it\n"]
