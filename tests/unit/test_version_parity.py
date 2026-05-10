"""Regression test: gencast.__version__ must match pyproject.toml's version.

The v1.0/v1.1/v1.2/v1.2.1 releases all shipped with `__version__ = '1.0.0a1'`
hardcoded in __init__.py — Click's `@version_option(__version__)` then reported
the wrong version on `gencast --version`, breaking the v1.2.1 version-gate
in every SKILL.md prereq check. This test ensures the source-of-truth is
single (pyproject.toml) and Click reflects it.
"""
from __future__ import annotations

import re
from pathlib import Path

import gencast


REPO_ROOT = Path(__file__).parent.parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_package_version_matches_pyproject():
    raw = PYPROJECT.read_text()
    match = re.search(r'^version = "([^"]+)"', raw, re.MULTILINE)
    assert match is not None, "pyproject.toml has no version line"
    pyproject_version = match.group(1)

    assert gencast.__version__ == pyproject_version, (
        f"gencast.__version__ ({gencast.__version__!r}) drifted from "
        f"pyproject.toml ({pyproject_version!r}). "
        "Run `pip install -e .` to refresh editable-install metadata."
    )


def test_version_is_pep440_parseable():
    """Sanity: the version string must look like a real version, not a sentinel."""
    assert re.match(r"^\d+\.\d+", gencast.__version__), (
        f"gencast.__version__ = {gencast.__version__!r} doesn't look like a version. "
        "Did `pip install -e .` succeed?"
    )
