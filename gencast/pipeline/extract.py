"""Source extraction — markdown / plain text. PDF + URL deferred to Plan C."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence

import tiktoken

if TYPE_CHECKING:
    from gencast.logger import Reporter

SOURCE_SEPARATOR = "\n\n---\n\n"
SUPPORTED_EXT = {".md", ".markdown", ".txt"}


def count_tokens(text: str, *, model: str) -> int:
    """Best-effort token count via tiktoken (falls back to cl100k_base)."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _read_one(path: Path) -> str:
    if path.suffix.lower() not in SUPPORTED_EXT:
        raise ValueError(
            f"Source format unsupported in Plan A: {path.suffix} "
            f"(supported: {sorted(SUPPORTED_EXT)}). PDF and URL extraction "
            f"land in Plan C."
        )
    return path.read_text(encoding="utf-8")


def extract_sources(
    paths: Sequence[str | Path],
    *,
    model: str,
    reporter: "Reporter | None" = None,
) -> tuple[str, int]:
    """
    Read sources, concatenate, return (text, token_count).
    Files are separated by `\\n\\n---\\n\\n` so the LLM knows they're distinct.
    """
    path_list = list(paths)
    if reporter is not None:
        reporter.stage_start(2, 10, "Extract", total_items=len(path_list))

    parts: list[str] = []
    for path_str in path_list:
        path = Path(path_str)
        if not path.is_file():
            raise FileNotFoundError(f"Source not found: {path}")
        parts.append(_read_one(path))
        if reporter is not None:
            reporter.stage_activity(f"reading {path}")
            reporter.stage_advance(1)

    text = SOURCE_SEPARATOR.join(parts)
    tokens = count_tokens(text, model=model)

    if reporter is not None:
        reporter.stage_done()

    return text, tokens
