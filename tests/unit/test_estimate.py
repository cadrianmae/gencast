# tests/unit/test_estimate.py
from pathlib import Path
import pytest


def test_stage_estimate_dataclass_shape():
    from gencast.pipeline.estimate import StageEstimate
    s = StageEstimate(stage="outline", provider="anthropic",
                      model="claude-haiku-4-5",
                      input_tokens=1000, output_tokens=600, usd=0.005)
    assert s.stage == "outline"
    assert s.usd == 0.005


def test_suggestion_dataclass_shape():
    from gencast.pipeline.estimate import Suggestion
    sug = Suggestion(stage="transcript",
                     current="anthropic/claude-sonnet-4-5",
                     alternative="anthropic/claude-haiku-4-5",
                     saves_usd=0.13, saves_pct=72, trade_off="quality")
    assert sug.saves_pct == 72


def test_estimate_dataclass_shape():
    from gencast.pipeline.estimate import Estimate
    est = Estimate(notebook_path=Path("nb.yaml"),
                   source_tokens=12840,
                   stages=[],
                   total_usd=0.37)
    assert est.uncertainty_pct == 25  # default
    assert est.suggestions == []      # default


def test_lookup_rate_known_anthropic_model():
    from gencast.pipeline.estimate import _lookup_rate
    rate = _lookup_rate("anthropic", "claude-haiku-4-5")
    # Either valid rates returned, or None if litellm has no entry
    assert rate is None or (rate.input_per_1k > 0 and rate.output_per_1k > 0)


def test_lookup_rate_unknown_model_returns_none():
    from gencast.pipeline.estimate import _lookup_rate
    assert _lookup_rate("anthropic", "totally-fake-model-xyz") is None


def test_lookup_rate_local_provider_returns_zero_rate():
    from gencast.pipeline.estimate import _lookup_rate
    rate = _lookup_rate("ollama", "llama3.2")
    assert rate is not None
    assert rate.input_per_1k == 0.0
    assert rate.output_per_1k == 0.0


def test_heuristic_constants_present():
    from gencast.pipeline import estimate as e
    assert e.OUTLINE_OUTPUT_TOKENS == 600
    assert e.WORDS_PER_SEGMENT == 150
    assert e.TOKENS_PER_WORD == 1.5
    assert e.OPENAI_TTS_HD_PER_1K_CHARS == 0.030
    assert e.OPENAI_WHISPER_PER_MINUTE == 0.006


def test_estimate_transcript_six_segments():
    from gencast.pipeline.estimate import (
        _estimate_transcript, WORDS_PER_SEGMENT, TOKENS_PER_WORD,
    )
    s = _estimate_transcript(
        provider="anthropic", model="claude-sonnet-4-5",
        source_tokens=12000, num_segments=6,
    )
    assert s.stage == "transcript"
    expected_output = int(6 * WORDS_PER_SEGMENT * TOKENS_PER_WORD)  # 1350
    assert s.output_tokens == expected_output
    assert s.input_tokens == 12000
    assert s.usd >= 0.0


def test_estimate_transcript_zero_segments_zero_output():
    from gencast.pipeline.estimate import _estimate_transcript
    s = _estimate_transcript(
        provider="anthropic", model="claude-sonnet-4-5",
        source_tokens=12000, num_segments=0,
    )
    assert s.output_tokens == 0
