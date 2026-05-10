"""Schema-aware streaming JSON filter — pumps complete top-level objects out of
an arriving JSON stream so reporters can render dialogue/segment lines instead
of raw JSON tokens.

Used by:
  - pipeline/transcript.py — emits "Speaker: text" per turn
  - pipeline/outline.py    — emits "name: description" per segment
"""
from __future__ import annotations

import json
from typing import Callable


def _all_balanced_objects(buf: str):
    """Yield (open_idx, close_idx_exclusive) for every balanced `{...}` in `buf`,
    regardless of nesting depth. Skips characters inside JSON strings (escape-
    aware). Yields outer objects after their inner ones (close-order), so
    callers should de-dup by start position.
    """
    in_string = False
    escape = False
    open_stack: list[int] = []
    for i, c in enumerate(buf):
        if escape:
            escape = False
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
            continue
        if c == "{":
            open_stack.append(i)
        elif c == "}":
            if open_stack:
                start = open_stack.pop()
                yield start, i + 1


class JsonObjectStreamFilter:
    """Wrap a chunk callback with brace-balanced JSON object extraction.

    For each complete `{...}` object that closes, attempt to `json.loads` it.
    On success, hand the dict to `on_object`. On failure, skip silently
    (likely a nested or partial object — not a top-level item).

    The outermost wrapper braces of the response (e.g. `{"turns": [...]}` or
    `{"segments": [...]}`) are themselves balanced objects but contain nothing
    the caller wants directly — `on_object` is called for them too, so the
    caller's callback should distinguish (e.g. require a specific field).
    """

    def __init__(self, on_object: Callable[[dict], None]):
        self._on_object = on_object
        self._buf = ""
        self._emitted_starts: set[int] = set()

    def feed(self, chunk: str) -> None:
        self._buf += chunk
        # Rescan from the beginning each feed (cheap relative to LLM latency
        # at our buffer sizes) and emit each newly-closed object once.
        for start, end in _all_balanced_objects(self._buf):
            if start in self._emitted_starts:
                continue
            try:
                obj = json.loads(self._buf[start:end])
            except (json.JSONDecodeError, ValueError):
                self._emitted_starts.add(start)  # don't re-attempt next feed
                continue
            self._emitted_starts.add(start)
            if isinstance(obj, dict):
                try:
                    self._on_object(obj)
                except Exception:
                    pass  # never let a callback bug abort the stream


def transcript_turn_emitter(emit_line: Callable[[str], None]) -> Callable[[dict], None]:
    """Return an on_object callback that emits 'Speaker: text\\n' per turn-shaped object."""
    def _on_object(obj: dict) -> None:
        speaker = obj.get("speaker")
        text = obj.get("text")
        if isinstance(speaker, str) and isinstance(text, str) and speaker and text:
            collapsed = " ".join(text.split())  # collapse internal newlines + whitespace
            emit_line(f"{speaker}: {collapsed}\n")
    return _on_object


def outline_segment_emitter(emit_line: Callable[[str], None]) -> Callable[[dict], None]:
    """Return an on_object callback that emits 'name: description\\n' per segment-shaped object."""
    def _on_object(obj: dict) -> None:
        name = obj.get("name")
        description = obj.get("description")
        if isinstance(name, str) and isinstance(description, str) and name and description:
            collapsed = " ".join(description.split())
            emit_line(f"{name}: {collapsed}\n")
    return _on_object
