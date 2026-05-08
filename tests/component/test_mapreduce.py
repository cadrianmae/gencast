"""Map-reduce summarisation with mocked LLM."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gencast.cost import CostMeter
from gencast.pipeline.mapreduce import (
    SummariseFailedError,
    summarise_recursive,
)


def _mock_response(content: str):
    r = MagicMock()
    r.content = content
    return r


def test_no_op_when_under_budget(cost_meter):
    """If source already fits, return unchanged with one pass."""
    text = "short content"
    out = summarise_recursive(
        text, budget_tokens=1000,
        summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
        cost_meter=cost_meter,
    )
    assert out == text


def test_one_pass_summarisation(cost_meter):
    """Source ~10K tokens, budget 5K → one pass of K chunks summarised."""
    long_text = ("This is a long text. " * 2000)  # ~10K tokens
    summary = "Compressed summary that fits."

    with patch("gencast.pipeline.mapreduce.chat_completion") as mock:
        mock.return_value = _mock_response(summary)
        out = summarise_recursive(
            long_text, budget_tokens=2000,
            summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
            cost_meter=cost_meter,
        )
    # At least one summarise call
    assert mock.call_count >= 1
    # Output is shorter
    assert len(out) < len(long_text)


def test_max_depth_bail(cost_meter):
    """If summaries don't shrink enough, raise after max_depth passes."""
    long_text = "x " * 50_000

    # Mock returns the same long text → never shrinks
    with patch("gencast.pipeline.mapreduce.chat_completion") as mock:
        mock.return_value = _mock_response(long_text)
        with pytest.raises(SummariseFailedError):
            summarise_recursive(
                long_text, budget_tokens=100,
                summarise_provider="anthropic", summarise_model="claude-haiku-4-5",
                cost_meter=cost_meter,
                max_depth=2,
            )
