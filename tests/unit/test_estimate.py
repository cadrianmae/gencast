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
