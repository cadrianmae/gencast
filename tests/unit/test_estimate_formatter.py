# tests/unit/test_estimate_formatter.py
from pathlib import Path
from gencast.pipeline.estimate import StageEstimate, Suggestion, Estimate


def _example_estimate(with_suggestions: bool = True) -> Estimate:
    stages = [
        StageEstimate(stage="extract", provider=None, model=None, usd=0.0),
        StageEstimate(stage="outline", provider="anthropic",
                      model="claude-haiku-4-5",
                      input_tokens=13000, output_tokens=600, usd=0.04),
        StageEstimate(stage="transcript", provider="anthropic",
                      model="claude-sonnet-4-5",
                      input_tokens=13000, output_tokens=1350, usd=0.18),
        StageEstimate(stage="tts", provider="openai", model="tts-1-hd",
                      characters=4500, usd=0.14),
        StageEstimate(stage="whisper", provider="openai", model="whisper-1",
                      duration_minutes=6.0, usd=0.04),
    ]
    suggestions = []
    if with_suggestions:
        suggestions = [Suggestion(
            stage="transcript",
            current="anthropic/claude-sonnet-4-5",
            alternative="anthropic/claude-haiku-4-5",
            saves_usd=0.13, saves_pct=72, trade_off="quality",
        )]
    return Estimate(
        notebook_path=Path("my-lecture.yaml"),
        source_tokens=12840,
        stages=stages,
        total_usd=0.40,
        suggestions=suggestions,
    )


def test_format_table_has_total_and_caveat():
    from gencast.cli.estimate_formatter import format_table
    out = format_table(_example_estimate())
    assert "my-lecture.yaml" in out
    assert "12,840" in out  # source tokens with thousands sep
    assert "Total:" in out
    assert "$0.40" in out
    assert "±25%" in out


def test_format_table_includes_all_stages():
    from gencast.cli.estimate_formatter import format_table
    out = format_table(_example_estimate())
    for label in ("Extract", "Outline", "Transcript", "TTS", "Whisper"):
        assert label in out, f"stage label {label!r} missing from table"


def test_format_table_emits_suggestion():
    from gencast.cli.estimate_formatter import format_table
    out = format_table(_example_estimate())
    assert "Cheaper alternatives" in out
    assert "claude-haiku-4-5" in out
    assert "-72%" in out


def test_format_table_no_suggestions_when_empty():
    from gencast.cli.estimate_formatter import format_table
    out = format_table(_example_estimate(with_suggestions=False))
    assert "Cheaper alternatives" not in out


def test_format_json_round_trips():
    import json
    from gencast.cli.estimate_formatter import format_json
    out = format_json(_example_estimate())
    parsed = json.loads(out)
    assert parsed["source_tokens"] == 12840
    assert parsed["total_usd"] == 0.40
    assert parsed["uncertainty_pct"] == 25
    assert len(parsed["stages"]) == 5
    # Stages keyed by name
    assert parsed["stages"]["transcript"]["usd"] == 0.18
    assert len(parsed["suggestions"]) == 1


def test_format_rates_table_includes_per_1k_columns():
    from gencast.cli.estimate_formatter import format_rates_table
    rates = {
        "anthropic/claude-haiku-4-5": {"input_per_1k": 0.001, "output_per_1k": 0.005},
        "openai/gpt-5-mini": {"input_per_1k": 0.0003, "output_per_1k": 0.0024},
    }
    out = format_rates_table(rates)
    assert "claude-haiku-4-5" in out
    assert "gpt-5-mini" in out
    assert "$0.0010" in out  # input rate appears formatted to 4 decimals
    assert "input/1k" in out.lower() or "input per 1k" in out.lower()


def test_format_rates_json_round_trips():
    import json
    from gencast.cli.estimate_formatter import format_rates_json
    rates = {"anthropic/claude-haiku-4-5": {"input_per_1k": 0.001, "output_per_1k": 0.005}}
    parsed = json.loads(format_rates_json(rates))
    assert parsed["anthropic/claude-haiku-4-5"]["input_per_1k"] == 0.001
