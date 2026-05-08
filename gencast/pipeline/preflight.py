"""Token-budget preflight. Map-reduce compression for over-budget sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gencast.cost import CostMeter

# Conservative budgets per model — context window minus headroom for prompt
# scaffolding, system messages, and response.
_MODEL_BUDGETS: dict[str, int] = {
    "anthropic/claude-sonnet-4":  200_000 - 5_000,
    "anthropic/claude-haiku-4.5": 200_000 - 5_000,
    "anthropic/claude-opus-4-7":  200_000 - 5_000,
    # NOTE: gpt-5-mini context window is speculative; revisit when published.
    "openai/gpt-5-mini":           400_000 - 5_000,
    "openai/gpt-4o-mini":          128_000 - 5_000,
    "openai/gpt-4o":               128_000 - 5_000,
}

# Conservative fallback for any model not in _MODEL_BUDGETS — chosen so an
# unknown model errs on the side of refusing oversized input rather than
# silently passing it through.
_DEFAULT_BUDGET = 100_000


class SourceTooLargeError(ValueError):
    def __init__(self, source_tokens: int, budget: int, model: str):
        self.source_tokens = source_tokens
        self.budget = budget
        self.model = model
        super().__init__(
            f"Source is {source_tokens:,} tokens, exceeds {model} input budget of "
            f"{budget:,} tokens. Plan C will add map-reduce compression. "
            f"For now: split the notebook, trim sources, or pick a model with a larger context."
        )


def model_input_budget(model: str) -> int:
    """Return conservative input-token budget for the given litellm model string."""
    return _MODEL_BUDGETS.get(model, _DEFAULT_BUDGET)


def preflight(*, source_tokens: int, model: str) -> None:
    """Raise SourceTooLargeError if the source exceeds the model's input budget."""
    budget = model_input_budget(model)
    if source_tokens > budget:
        raise SourceTooLargeError(source_tokens, budget, model)


def compress_if_needed(
    *,
    source_text: str,
    source_tokens: int,
    target_model: str,
    summarise_provider: str,
    summarise_model: str,
    cost_meter: "CostMeter",
) -> tuple[str, int]:
    """Run map-reduce if source exceeds target_model budget. Returns (text, tokens)."""
    from gencast.pipeline.mapreduce import summarise_recursive

    budget = model_input_budget(target_model)
    if source_tokens <= budget:
        return source_text, source_tokens
    compressed = summarise_recursive(
        source_text,
        budget_tokens=budget,
        summarise_provider=summarise_provider,
        summarise_model=summarise_model,
        cost_meter=cost_meter,
    )
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    new_tokens = len(enc.encode(compressed))
    return compressed, new_tokens
