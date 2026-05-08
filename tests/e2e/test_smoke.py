# tests/e2e/test_smoke.py
"""End-to-end smoke against real APIs. Env-gated."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from gencast.notebook import load_notebook
from gencast.pipeline import run_pipeline

pytestmark = pytest.mark.skipif(
    os.environ.get("GENCAST_TEST_E2E") != "1",
    reason="GENCAST_TEST_E2E=1 not set (real-API run, costs ~$0.20)",
)


def test_smoke_notebook_end_to_end(tmp_path):
    src_fixtures = Path(__file__).parent.parent / "fixtures" / "notebooks"
    shutil.copy(src_fixtures / "smoke.yaml", tmp_path / "smoke.yaml")
    shutil.copy(src_fixtures / "smoke_source.md", tmp_path / "smoke_source.md")

    nb_path = tmp_path / "smoke.yaml"
    nb = load_notebook(nb_path)
    nb.output.dir = tmp_path / "out"
    nb.sources = [str((nb_path.parent / s).resolve()) for s in nb.sources]
    nb.output.formats = ["mp3", "transcript", "cost"]  # avoid m4a in CI

    state = run_pipeline(nb)

    assert state.outline is not None
    assert state.transcript is not None
    assert state.combined_audio is not None
    assert len(state.clips) > 0
    assert state.cost.total_usd < 0.50  # cap at 50¢ for the test fixture

    out = nb.output.dir
    assert (out / "smoke.mp3").exists()
    assert (out / "smoke.srt").exists()
    assert (out / "smoke.transcript.json").exists()
    assert (out / "smoke.cost.json").exists()
