"""LLM disk cache get/put roundtrip and key uniqueness."""

from __future__ import annotations

import json
from pathlib import Path

from gencast.llm.cache import LLMDiskCache


def test_miss_returns_none(tmp_path):
    cache = LLMDiskCache(tmp_path)
    out = cache.get(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        params={"max_tokens": 100},
    )
    assert out is None


def test_hit_after_put(tmp_path):
    cache = LLMDiskCache(tmp_path)
    payload = {
        "content": "hello",
        "tokens_in": 5, "tokens_out": 1,
        "cache_reads_in": 0, "cache_writes_in": 0,
        "usd": 0.001,
    }
    cache.put(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        params={"max_tokens": 100},
        payload=payload,
    )
    got = cache.get(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        params={"max_tokens": 100},
    )
    assert got == payload


def test_different_messages_miss(tmp_path):
    cache = LLMDiskCache(tmp_path)
    cache.put(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "A"}],
        params={"max_tokens": 100},
        payload={"content": "a", "tokens_in": 1, "tokens_out": 1,
                 "cache_reads_in": 0, "cache_writes_in": 0, "usd": 0.001},
    )
    assert cache.get(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "B"}],
        params={"max_tokens": 100},
    ) is None


def test_malformed_json_returns_none(tmp_path):
    cache = LLMDiskCache(tmp_path)
    # Manually create a cache file with corrupt JSON
    p = cache._path(cache._key(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "corrupt"}],
        params={"max_tokens": 100},
    ))
    p.write_text("{invalid json garbage")

    # get() should return None (cache miss) instead of raising
    result = cache.get(
        provider="anthropic", model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "corrupt"}],
        params={"max_tokens": 100},
    )
    assert result is None
