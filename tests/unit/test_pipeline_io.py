"""JSON sidecar writers."""

from __future__ import annotations

import json

from gencast.pipeline.io import (
    write_cost_json,
    write_outline_json,
    write_transcript_json,
)


def test_write_outline_json(tmp_path, sample_state_with_outline):
    p = tmp_path / "out.outline.json"
    write_outline_json(sample_state_with_outline, p)
    data = json.loads(p.read_text())
    assert data["title"] == sample_state_with_outline.notebook.title
    assert len(data["segments"]) == 2
    assert data["segments"][0]["name"] == "Intro"


def test_write_transcript_json(tmp_path, sample_state_with_transcript):
    p = tmp_path / "out.transcript.json"
    write_transcript_json(sample_state_with_transcript, p)
    data = json.loads(p.read_text())
    assert data["title"] == sample_state_with_transcript.notebook.title
    assert data["speakers"] == ["Sophie", "Ben"]
    assert data["duration_ms"] == 0  # no clips yet
    assert len(data["turns"]) == 2
    assert data["turns"][0]["speaker"] == "Sophie"
    assert data["turns"][0]["segment_index"] == 0


def test_write_cost_json(tmp_path, sample_state_with_outline):
    sample_state_with_outline.cost.record_llm(
        "outline", model="anthropic/claude-haiku-4.5",
        tokens_in=100, tokens_out=20, usd=0.001,
    )
    p = tmp_path / "out.cost.json"
    write_cost_json(sample_state_with_outline, p)
    data = json.loads(p.read_text())
    assert "stages" in data
    assert "outline" in data["stages"]
    assert data["total_usd"] > 0
