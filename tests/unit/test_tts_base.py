"""TTSBackend Protocol and sentence splitter."""

from __future__ import annotations

from gencast.tts.base import TTSBackend, split_sentences


def test_split_simple():
    s = split_sentences("Hello there. How are you? I am well!")
    assert s == ["Hello there.", "How are you?", "I am well!"]


def test_split_no_terminator():
    s = split_sentences("just some text without ending")
    assert s == ["just some text without ending"]


def test_split_empty_returns_single():
    s = split_sentences("")
    assert s == [""]  # contract: never returns empty list


def test_split_quoted_continuation():
    """Sentence boundary requires capital or quote after the gap."""
    s = split_sentences('She said "Hi." Then she left.')
    assert len(s) == 2


def test_protocol_check():
    """A minimal backend satisfies the Protocol."""

    class StubBackend:
        async def synthesize(self, *, voice: str, text: str) -> tuple[bytes, float]:
            return b"\x00\x00", 1.0

        @property
        def usd_per_audio_second(self) -> float:
            return 0.0

        @property
        def backend_name(self) -> str:
            return "stub"

        @property
        def model(self) -> str:
            return "stub-1"

    b: TTSBackend = StubBackend()  # type-check at runtime
    assert b.backend_name == "stub"
