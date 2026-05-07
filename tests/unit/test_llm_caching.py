"""Tests for cache_control message construction."""

from __future__ import annotations

from gencast.llm.caching import build_cached_messages


def test_anthropic_marks_prefix_with_cache_control():
    msgs = build_cached_messages(
        provider="anthropic", prefix="PREFIX_TEXT", suffix="SUFFIX_TEXT",
    )
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["role"] == "user"
    parts = msg["content"]
    assert isinstance(parts, list)
    assert len(parts) == 2
    assert parts[0]["type"] == "text"
    assert parts[0]["text"] == "PREFIX_TEXT"
    assert parts[0]["cache_control"] == {"type": "ephemeral"}
    assert parts[1]["type"] == "text"
    assert parts[1]["text"] == "SUFFIX_TEXT"
    assert "cache_control" not in parts[1]


def test_non_anthropic_uses_plain_string():
    msgs = build_cached_messages(
        provider="openai", prefix="PREFIX", suffix="SUFFIX",
    )
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "PREFIX\n\nSUFFIX"


def test_anthropic_empty_suffix_still_two_blocks():
    msgs = build_cached_messages(
        provider="anthropic", prefix="P", suffix="",
    )
    parts = msgs[0]["content"]
    assert len(parts) == 2
    assert parts[1]["text"] == ""
