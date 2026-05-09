"""Force tests/skills/* subprocess.run("gencast", ...) calls to resolve to the
worktree's editable install, not any system-wide gencast on the ambient PATH."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
VENV_BIN = REPO_ROOT / "venv" / "bin"


@pytest.fixture(scope="session", autouse=True)
def _prepend_venv_bin_to_path():
    if not VENV_BIN.exists():
        pytest.skip(f"venv/bin not found at {VENV_BIN} — run pip install -e . first")
    original = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{VENV_BIN}{os.pathsep}{original}"
    yield
    os.environ["PATH"] = original
