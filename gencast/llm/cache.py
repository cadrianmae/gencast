"""Disk-backed LLM response cache (opt-in via --cache-llm)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class LLMDiskCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _key(
        self, *, provider: str, model: str,
        messages: list[dict], params: dict,
    ) -> str:
        key_input = json.dumps(
            [provider, model, messages, params],
            sort_keys=True, default=str,
        )
        return hashlib.sha256(key_input.encode()).hexdigest()[:32]

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(
        self, *, provider: str, model: str,
        messages: list[dict], params: dict,
    ) -> dict[str, Any] | None:
        p = self._path(self._key(
            provider=provider, model=model, messages=messages, params=params,
        ))
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None

    def put(
        self, *, provider: str, model: str,
        messages: list[dict], params: dict,
        payload: dict[str, Any],
    ) -> None:
        p = self._path(self._key(
            provider=provider, model=model, messages=messages, params=params,
        ))
        tmp = p.with_suffix(p.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(payload))
            os.replace(tmp, p)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise


def default_llm_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "gencast" / "llm"
