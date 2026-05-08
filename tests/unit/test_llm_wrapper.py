from unittest.mock import patch, MagicMock
import pytest
from gencast.llm import chat_completion, LLMResponse
from gencast.cost import CostMeter


def _mock_litellm_response(content: str = "ok", tokens_in: int = 100, tokens_out: int = 50):
    """Build a mock litellm response shape."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = tokens_in
    resp.usage.completion_tokens = tokens_out
    resp.usage.cache_read_input_tokens = 0
    resp.usage.cache_creation_input_tokens = 0
    resp._hidden_params = {"response_cost": 0.001}
    return resp


def test_chat_completion_returns_text_and_usage():
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response("hello world")
        result = chat_completion(
            provider="anthropic", model="claude-haiku-4.5",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert isinstance(result, LLMResponse)
        assert result.content == "hello world"
        assert result.tokens_in == 100
        assert result.tokens_out == 50
        assert result.usd == pytest.approx(0.001)


def test_chat_completion_records_cost():
    cm = CostMeter()
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response()
        chat_completion(
            provider="anthropic", model="claude-haiku-4.5",
            messages=[{"role": "user", "content": "hi"}],
            cost_meter=cm, stage="outline",
        )
    assert "outline" in cm.stages
    assert cm.stages["outline"].tokens_in == 100


def test_chat_completion_passes_response_format():
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response('{"k":"v"}')
        chat_completion(
            provider="anthropic", model="claude-haiku-4.5",
            messages=[{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
        kwargs = mock.call_args.kwargs
        assert kwargs["response_format"] == {"type": "json_object"}


def test_chat_completion_combines_provider_model():
    """litellm wants 'anthropic/claude-haiku-4.5', not separate provider+model."""
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response()
        chat_completion(
            provider="anthropic", model="claude-haiku-4.5",
            messages=[{"role": "user", "content": "hi"}],
        )
        kwargs = mock.call_args.kwargs
        assert kwargs["model"] == "anthropic/claude-haiku-4.5"


def test_chat_completion_openai_no_provider_prefix():
    """OpenAI models don't take a provider prefix in litellm."""
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response()
        chat_completion(
            provider="openai", model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
        )
        kwargs = mock.call_args.kwargs
        assert kwargs["model"] == "gpt-4o-mini"
