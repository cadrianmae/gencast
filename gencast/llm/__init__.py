"""LiteLLM wrapper — chat completion + usage extraction + cost tracking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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
    cache_dir: Path | None = None,
    on_chunk: Callable[[str], None] | None = None,
) -> LLMResponse:
    """One LLM call. Records cost into cost_meter[stage] if provided.

    When `on_chunk` is provided, switches to streaming mode and pumps each
    text delta into the callback as it arrives. Cache hits emit the full
    cached content as a single chunk so the UX is consistent.
    """
    params = {
        "response_format": response_format,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "extra": extra,
    }

    cache = None
    if cache_dir is not None:
        from gencast.llm.cache import LLMDiskCache
        cache = LLMDiskCache(cache_dir)
        cached = cache.get(provider=provider, model=model, messages=messages, params=params)
        if cached is not None:
            if on_chunk is not None:
                on_chunk(cached["content"])
            return LLMResponse(
                content=cached["content"],
                tokens_in=cached["tokens_in"],
                tokens_out=cached["tokens_out"],
                cache_reads_in=cached["cache_reads_in"],
                cache_writes_in=cached["cache_writes_in"],
                usd=cached["usd"],
                raw=None,
            )

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

    if on_chunk is not None:
        # Streaming branch — pump deltas to the callback, accumulate into resp.
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
        chunks: list[str] = []
        usage = None
        last = None
        for piece in completion(**kwargs):
            last = piece
            if getattr(piece, "usage", None) is not None:
                usage = piece.usage
            try:
                delta = piece.choices[0].delta.content
            except (AttributeError, IndexError):
                delta = None
            if delta:
                chunks.append(delta)
                on_chunk(delta)
        content = "".join(chunks)
        resp = last
        tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0
        cache_reads_in = (getattr(usage, "cache_read_input_tokens", 0) or 0) if usage else 0
        cache_writes_in = (getattr(usage, "cache_creation_input_tokens", 0) or 0) if usage else 0
        usd = ((resp._hidden_params or {}).get("response_cost", 0.0) or 0.0) if resp else 0.0
    else:
        resp = completion(**kwargs)
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        tokens_in = getattr(usage, "prompt_tokens", 0)
        tokens_out = getattr(usage, "completion_tokens", 0)
        cache_reads_in = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_writes_in = getattr(usage, "cache_creation_input_tokens", 0) or 0
        usd = (resp._hidden_params or {}).get("response_cost", 0.0) or 0.0

    if cache is not None:
        cache.put(
            provider=provider, model=model, messages=messages, params=params,
            payload={
                "content": content,
                "tokens_in": tokens_in, "tokens_out": tokens_out,
                "cache_reads_in": cache_reads_in, "cache_writes_in": cache_writes_in,
                "usd": usd,
            },
        )

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
