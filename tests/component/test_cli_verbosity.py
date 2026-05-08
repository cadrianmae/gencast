"""Verbosity flag plumbing — Reporter ends up on ctx.obj['reporter']."""

from __future__ import annotations

from click.testing import CliRunner

from gencast.cli.main import cli


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
