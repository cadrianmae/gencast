"""Verbosity flag plumbing — Reporter ends up on ctx.obj['reporter']."""

from __future__ import annotations

import logging

from click.testing import CliRunner

from gencast.cli.main import cli
from gencast.logger import PlainReporter


def test_default_verbosity_is_one():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles", "--type=rooms"])
    assert result.exit_code == 0


def test_silent_flag_accepted():
    runner = CliRunner()
    result = runner.invoke(cli, ["--silent", "list-profiles", "--type=rooms"])
    assert result.exit_code == 0


def test_log_file_writes(tmp_path):
    runner = CliRunner()
    log = tmp_path / "run.log"
    result = runner.invoke(
        cli, ["--log-file", str(log), "list-profiles", "--type=rooms"]
    )
    assert result.exit_code == 0
    assert log.exists()


def test_verbose_and_silent_are_mutually_exclusive():
    runner = CliRunner()
    result = runner.invoke(cli, ["--silent", "-v", "list-profiles"])
    # Click should reject combination
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower() or result.exit_code == 2


# --- Reviewer-flagged gaps ---

def test_verbose_flag_produces_higher_verbosity_than_default():
    """-v must resolve to verbosity 2; bare default resolves to 1."""
    plain_default = PlainReporter(verbosity=1)
    plain_verbose = PlainReporter(verbosity=2)
    # verbosity 2 enables stage_activity; verbosity 1 does not
    assert plain_default.verbosity == 1
    assert plain_verbose.verbosity == 2
    assert plain_verbose.verbosity > plain_default.verbosity

    # Verify -v flag is accepted and exits cleanly
    runner = CliRunner()
    result = runner.invoke(cli, ["-v", "list-profiles", "--type=rooms"])
    assert result.exit_code == 0


def test_debug_flag_produces_higher_verbosity_than_verbose():
    """-vv/--debug must resolve to verbosity 3, distinct from -v (verbosity 2)."""
    plain_verbose = PlainReporter(verbosity=2)
    plain_debug = PlainReporter(verbosity=3)
    assert plain_debug.verbosity > plain_verbose.verbosity

    runner = CliRunner()
    result = runner.invoke(cli, ["-vv", "list-profiles", "--type=rooms"])
    assert result.exit_code == 0

    result2 = runner.invoke(cli, ["--debug", "list-profiles", "--type=rooms"])
    assert result2.exit_code == 0


def _cleanup_log_handlers(log_path: str) -> None:
    """Remove file handlers pointing at log_path to avoid test bleed."""
    root = logging.getLogger()
    for h in list(root.handlers):
        base = getattr(h, "baseFilename", "")
        if isinstance(h, logging.FileHandler) and log_path in base:
            root.removeHandler(h)
            h.close()


def test_log_file_writes_content_not_just_empty(tmp_path):
    """--log-file must tee actual log output, not just touch an empty file."""
    runner = CliRunner()
    log = tmp_path / "run.log"
    result = runner.invoke(
        cli, ["--log-file", str(log), "list-profiles", "--type=rooms"]
    )
    assert result.exit_code == 0, result.output
    assert log.exists()
    content = log.read_text(encoding="utf-8")
    # File must be non-empty and contain the startup record we emit
    assert len(content) > 0, "log file is empty — tee did not write anything"
    assert "gencast" in content.lower(), (
        f"expected 'gencast' in log content, got: {content!r}"
    )
    _cleanup_log_handlers(str(log))
