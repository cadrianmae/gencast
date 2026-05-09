"""Calibration: predicted vs actual cost on the smoke notebook.

Costs ~$0.20 per run. Gated on GENCAST_TEST_E2E=1 (same gate as the existing
end-to-end smoke). Asserts predicted within 30% of actual.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("GENCAST_TEST_E2E") != "1",
    reason="GENCAST_TEST_E2E=1 not set (calibration runs spend real money)",
)


def test_estimate_within_30pct_of_actual(tmp_path: Path):
    from gencast.notebook import load_notebook
    from gencast.pipeline import run_pipeline
    from gencast.pipeline.estimate import estimate_notebook

    nb = load_notebook("tests/fixtures/notebooks/smoke.yaml")
    predicted = estimate_notebook(nb).total_usd
    state = run_pipeline(nb)
    actual = state.cost.total_usd

    assert predicted > 0
    assert actual > 0
    delta_pct = abs(predicted - actual) / actual
    assert delta_pct < 0.30, (
        f"estimate predicted ${predicted:.4f}, actual ${actual:.4f}, "
        f"delta {delta_pct:.0%} — exceeds 30% calibration threshold."
    )
