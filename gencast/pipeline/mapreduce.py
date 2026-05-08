"""Recursive map-reduce summarisation for sources that exceed model context."""

from __future__ import annotations

from gencast.cost import CostMeter
from gencast.llm import chat_completion


class SummariseFailedError(RuntimeError):
    """Raised when source still exceeds budget after max_depth passes."""


_SUMMARISE_PROMPT = """\
Summarise the following content. Preserve every named concept, named entity,
formula, definition, and example. Reduce phrasing to its tightest accurate form.
Return only the summary — no commentary, no preamble.

<content>
{content}
</content>
"""


def _count_tokens(text: str, model: str) -> int:
    """Rough token count via tiktoken's cl100k_base. Same as preflight."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _split_into_chunks(text: str, target_tokens: int) -> list[str]:
    """Split text on paragraph boundaries into chunks ≤ target_tokens each."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for p in paragraphs:
        p_tokens = len(enc.encode(p))
        if current_tokens + p_tokens > target_tokens and current:
            chunks.append("\n\n".join(current))
            current = [p]
            current_tokens = p_tokens
        else:
            current.append(p)
            current_tokens += p_tokens
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def summarise_recursive(
    text: str,
    *,
    budget_tokens: int,
    summarise_provider: str,
    summarise_model: str,
    cost_meter: CostMeter,
    chunk_tokens: int = 4000,
    max_depth: int = 3,
) -> str:
    """Recursively summarise until text fits within budget_tokens."""
    for depth in range(max_depth):
        current_tokens = _count_tokens(text, f"{summarise_provider}/{summarise_model}")
        if current_tokens <= budget_tokens:
            return text

        chunks = _split_into_chunks(text, target_tokens=chunk_tokens)
        summaries: list[str] = []
        for chunk in chunks:
            response = chat_completion(
                provider=summarise_provider,
                model=summarise_model,
                messages=[{
                    "role": "user",
                    "content": _SUMMARISE_PROMPT.format(content=chunk),
                }],
                max_tokens=2000,
                cost_meter=cost_meter,
                stage="map_reduce",
            )
            summaries.append(response.content.strip())

        text = "\n\n".join(summaries)

    final_tokens = _count_tokens(text, f"{summarise_provider}/{summarise_model}")
    if final_tokens > budget_tokens:
        raise SummariseFailedError(
            f"Source still {final_tokens:,} tokens after {max_depth} passes "
            f"(budget {budget_tokens:,}). Trim sources or pick a model with larger context."
        )
    return text
