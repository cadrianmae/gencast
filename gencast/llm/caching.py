"""Anthropic ephemeral prompt-cache helper.

LiteLLM passes `cache_control` blocks straight through to Anthropic. For other
providers we emit a plain string (LiteLLM ignores cache_control on them, but
content-list shape is not always supported, so we play safe).
"""

from __future__ import annotations

from typing import Any


def build_cached_messages(
    *, provider: str, prefix: str, suffix: str,
) -> list[dict[str, Any]]:
    """
    Build a single-user-message payload that caches `prefix` for Anthropic.

    On Anthropic the message uses content-list form with a cache_control marker
    on the prefix block. On other providers we concatenate prefix+suffix into a
    plain string for maximum compatibility.
    """
    if provider == "anthropic":
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prefix,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": suffix},
                ],
            }
        ]
    return [{"role": "user", "content": f"{prefix}\n\n{suffix}"}]
