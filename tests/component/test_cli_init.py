"""Wizard test using CliRunner.input."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gencast.cli.main import cli


def test_init_minimal_writes_notebook_yaml(tmp_path):
    runner = CliRunner()
    # Create a fake source file the wizard can resolve
    src = tmp_path / "lecture.md"
    src.write_text("# Test\n")
    inputs = "\n".join([
        "Test Notebook",  # title
        str(src),          # one source path
        "",                # blank to finish source list
        "1",               # speaker profile picker (1=first option)
        "1",               # episode profile picker
        "1",               # room profile picker
        "m4a",             # output format
        "",                # blank briefing
    ]) + "\n"
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        result = runner.invoke(cli, ["init", "--minimal"], input=inputs)
        assert result.exit_code == 0, result.output
        nb_path = Path(cwd) / "notebook.yaml"
        assert nb_path.exists()
        content = nb_path.read_text()
        assert "Test Notebook" in content
        assert "lecture.md" in content


def test_init_refuses_to_overwrite_existing(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        existing = Path(cwd) / "notebook.yaml"
        existing.write_text("title: existing\n")
        result = runner.invoke(cli, ["init", "--minimal"], input="\n" * 10)
        # Should fail with clear error rather than silently overwrite
        assert result.exit_code != 0
        assert "exists" in result.output.lower()
