"""Test _TurnStreamFilter — schema-aware streaming JSON parser for transcript previews."""
from __future__ import annotations

from gencast.pipeline.transcript import _TurnStreamFilter


def _feed(chunks: list[str]) -> list[str]:
    out: list[str] = []
    f = _TurnStreamFilter(out.append)
    for c in chunks:
        f.feed(c)
    return out


def test_emits_one_line_per_complete_turn():
    chunks = [
        '{"turns": [',
        '{"speaker": "Alex", "text": "Hello world"}',
        ', {"speaker": "Sam", "text": "Hi there"}',
        ']}',
    ]
    assert _feed(chunks) == [
        "Alex: Hello world\n",
        "Sam: Hi there\n",
    ]


def test_chunk_split_mid_turn_does_not_emit_until_complete():
    """A turn that's only half-arrived must not emit until the closing brace lands."""
    chunks = [
        '{"turns": [{"speaker": "Alex", "text": "Hello',
        ' world"}',  # closing brace arrives only here
    ]
    out = _feed(chunks[:1])
    assert out == []  # no emit yet
    f = _TurnStreamFilter(out.append)
    f.feed(chunks[0])
    f.feed(chunks[1])
    assert out == ["Alex: Hello world\n"]


def test_strips_code_fence_and_handles_escapes():
    chunks = [
        '```json\n{"turns": [',
        r'{"speaker": "Alex", "text": "She said \"hi\""}',
        r', {"speaker": "Sam", "text": "Newline\nhere"}',
        ']}\n```',
    ]
    out = _feed(chunks)
    assert out[0] == 'Alex: She said "hi"\n'
    assert out[1] == 'Sam: Newline here\n'  # \n collapses to space


def test_does_not_re_emit_already_seen_turns():
    """A second feed() call must not duplicate turns from the first."""
    f_out: list[str] = []
    f = _TurnStreamFilter(f_out.append)
    f.feed('{"turns": [{"speaker": "Alex", "text": "first"}')
    assert f_out == ["Alex: first\n"]
    f.feed(', {"speaker": "Sam", "text": "second"}]}')
    assert f_out == ["Alex: first\n", "Sam: second\n"]


def test_empty_or_partial_speaker_does_not_emit():
    """Incomplete turn structure should be ignored, not partial-emitted."""
    chunks = ['{"turns": [{"speaker": "Alex", "text":']  # text not even started
    assert _feed(chunks) == []
