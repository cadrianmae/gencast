"""Smoke tests for the gencast Claude Code skills.

Each skill's workflow shells out to specific gencast CLI commands. These
tests verify those CLI calls still produce the contracts the skills
depend on, so breakage in gencast surfaces here at gencast-test time
rather than at user-skill-invocation time.

Tests run gencast as an installed CLI (the editable install in the trunk
venv). Each test is fast (< 2s) and uses no real API calls.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent
SMOKE_NB = REPO_ROOT / "tests" / "fixtures" / "notebooks" / "smoke.yaml"


def _run(*args: str) -> tuple[int, str, str]:
    """Run gencast with the given args; return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["gencast", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def test_gencast_version_works():
    """All four skills check `gencast --version` as a prereq."""
    code, out, _ = _run("--version")
    assert code == 0
    assert "gencast" in out.lower()


def test_notebook_init_skill_dependencies():
    """`notebook-init` injects `gencast list-profiles --json`."""
    code, out, _ = _run("list-profiles", "--json")
    assert code == 0
    profiles = json.loads(out)
    assert isinstance(profiles, list)
    assert len(profiles) > 0
    sample = profiles[0]
    assert "kind" in sample
    assert "name" in sample


def test_source_check_skill_dependencies():
    """`source-check` calls `gencast list-profiles --type episodes --json`
    and `gencast estimate <NB> --json`."""
    code, out, _ = _run("list-profiles", "--type", "episodes", "--json")
    assert code == 0
    episodes = json.loads(out)
    assert all(p.get("kind") == "episodes" for p in episodes)

    code, out, _ = _run("estimate", str(SMOKE_NB), "--json")
    assert code == 0, f"estimate failed: {out}"
    est = json.loads(out)
    for required in ("total_usd", "source_tokens", "stages", "suggestions"):
        assert required in est


def test_review_transcript_skill_dependencies():
    """`review-transcript` only checks `gencast --version` (it operates
    on a user-supplied transcript.json without further gencast calls).
    Already covered by test_gencast_version_works."""
    pass


def test_cost_explain_skill_dependencies():
    """`cost-explain` injects `gencast estimate --rates-only --json` and
    optionally calls `gencast estimate <NB> --json`."""
    code, out, _ = _run("estimate", "--rates-only", "--json")
    assert code == 0
    rates = json.loads(out)
    assert isinstance(rates, dict)
    assert len(rates) > 0
    sample_key = next(iter(rates))
    assert "input_per_1k" in rates[sample_key]
    assert "output_per_1k" in rates[sample_key]
