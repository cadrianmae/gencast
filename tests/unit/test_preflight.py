import pytest
from gencast.pipeline.preflight import preflight, SourceTooLargeError, model_input_budget


def test_model_input_budget_known_models():
    assert model_input_budget("anthropic/claude-sonnet-4-5") == 200_000 - 5_000
    assert model_input_budget("openai/gpt-5-mini") > 0
    assert model_input_budget("anthropic/claude-haiku-4-5") == 200_000 - 5_000


def test_model_input_budget_unknown_returns_default():
    n = model_input_budget("unknown/model")
    assert n == 100_000


def test_preflight_passes_when_fits():
    preflight(source_tokens=5_000, model="anthropic/claude-sonnet-4-5")


def test_preflight_raises_when_oversize():
    with pytest.raises(SourceTooLargeError) as ei:
        preflight(source_tokens=300_000, model="anthropic/claude-sonnet-4-5")
    assert "300000" in str(ei.value) or "300,000" in str(ei.value)
    assert "claude-sonnet-4-5" in str(ei.value)
