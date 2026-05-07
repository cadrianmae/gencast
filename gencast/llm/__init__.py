"""LiteLLM wrapper — chat completion + usage extraction + cost tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from litellm import completion

from gencast.cost import CostMeter


@dataclass
class LLMResponse:
    content: str
    tokens_in: int
    tokens_out: int
    cache_reads_in: int
    cache_writes_in: int
    usd: float
    raw: Any  # full litellm response, for callers that need extra fields


def _format_model(provider: str, model: str) -> str:
    """litellm uses 'provider/model' for non-OpenAI; 'model' alone for OpenAI."""
    if provider == "openai":
        return model
    return f"{provider}/{model}"


def chat_completion(
    *,
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
    response_format: dict[str, Any] | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    extra: dict[str, Any] | None = None,
    cost_meter: CostMeter | None = None,
    stage: str | None = None,
) -> LLMResponse:
    """One LLM call. Records cost into cost_meter[stage] if provided."""
    kwargs: dict[str, Any] = {
        "model": _format_model(provider, model),
        "messages": messages,
        "num_retries": 3,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    if extra:
        kwargs.update(extra)

    resp = completion(**kwargs)

    content = resp.choices[0].message.content or ""
    usage = resp.usage
    tokens_in = getattr(usage, "prompt_tokens", 0)
    tokens_out = getattr(usage, "completion_tokens", 0)
    cache_reads_in = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_writes_in = getattr(usage, "cache_creation_input_tokens", 0) or 0
    usd = (resp._hidden_params or {}).get("response_cost", 0.0) or 0.0

    if cost_meter is not None and stage is not None:
        cost_meter.record_llm(
            stage,
            model=_format_model(provider, model),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cache_reads_in=cache_reads_in,
            cache_writes_in=cache_writes_in,
            usd=usd,
        )

    return LLMResponse(
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_reads_in=cache_reads_in,
        cache_writes_in=cache_writes_in,
        usd=usd,
        raw=resp,
    )
