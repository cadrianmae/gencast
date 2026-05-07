"""TTS disk cache — sha256 keying, miss/hit semantics."""

from __future__ import annotations

from gencast.tts.cache import TTSDiskCache


def test_miss_returns_none(tmp_path):
    cache = TTSDiskCache(tmp_path)
    assert cache.get(provider="openai", model="tts-1-hd", voice="nova", text="hello") is None


def test_hit_after_put(tmp_path):
    cache = TTSDiskCache(tmp_path)
    payload = b"\x00\x01\x02\x03"
    cache.put(provider="openai", model="tts-1-hd", voice="nova", text="hi", audio_bytes=payload)
    got = cache.get(provider="openai", model="tts-1-hd", voice="nova", text="hi")
    assert got == payload


def test_different_text_misses(tmp_path):
    cache = TTSDiskCache(tmp_path)
    cache.put(provider="openai", model="tts-1-hd", voice="nova", text="A", audio_bytes=b"a")
    assert cache.get(provider="openai", model="tts-1-hd", voice="nova", text="B") is None


def test_different_voice_misses(tmp_path):
    cache = TTSDiskCache(tmp_path)
    cache.put(provider="openai", model="tts-1-hd", voice="nova", text="A", audio_bytes=b"a")
    assert cache.get(provider="openai", model="tts-1-hd", voice="echo", text="A") is None


def test_layout(tmp_path):
    cache = TTSDiskCache(tmp_path)
    cache.put(provider="openai", model="tts-1-hd", voice="nova", text="A", audio_bytes=b"a")
    files = list(tmp_path.rglob("*.mp3"))
    assert len(files) == 1
    rel = files[0].relative_to(tmp_path)
    assert rel.parts[0] == "openai"
    assert rel.parts[1] == "tts-1-hd"
    assert rel.parts[2] == "nova"
    assert rel.parts[3].endswith(".mp3")
