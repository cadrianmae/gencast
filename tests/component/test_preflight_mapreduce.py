"""Preflight invokes map-reduce summarisation when source exceeds budget."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.cost import CostMeter
from gencast.pipeline.preflight import compress_if_needed


def _mock_response(content: str):
    r = MagicMock()
    r.content = content
    return r


def test_compress_if_needed_no_op_when_under_budget(cost_meter):
    text = "small text"
    out, tokens = compress_if_needed(
        source_text=text, source_tokens=10,
        target_model="anthropic/claude-sonnet-4-5",
        summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
        cost_meter=cost_meter,
    )
    assert out == text
    assert tokens == 10


def test_compress_if_needed_summarises_when_over(cost_meter):
    """Big source → calls summariser, returns compressed text + new token count."""
    long_text = "long content. " * 80_000
    summary = "compact summary"

    with patch("gencast.pipeline.mapreduce.chat_completion") as mock:
        mock.return_value = _mock_response(summary)
        out, tokens = compress_if_needed(
            source_text=long_text, source_tokens=200_000,
            target_model="anthropic/claude-sonnet-4-5",
            summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
            cost_meter=cost_meter,
        )
    assert len(out) < len(long_text)
    assert tokens < 200_000
