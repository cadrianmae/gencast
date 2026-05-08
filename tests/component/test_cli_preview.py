from unittest.mock import patch
from pathlib import Path
import pytest
from click.testing import CliRunner
from gencast.cli.main import cli


@pytest.fixture
def sample_notebook_file(tmp_path):
    src = tmp_path / "lecture.md"
    src.write_text("Some interesting content about a topic.")
    nb = tmp_path / "nb.yaml"
    nb.write_text(
        f"title: Test podcast\n"
        f"sources: [{src}]\n"
    )
    return nb


def test_preview_smoke(sample_notebook_file, mock_llm_outline_response):
    runner = CliRunner()
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        result = runner.invoke(cli, ["preview", str(sample_notebook_file)])
    assert result.exit_code == 0, result.output
    assert "Outline" in result.output or "segments" in result.output.lower()


def test_preview_shows_segment_names(sample_notebook_file, mock_llm_outline_response):
    runner = CliRunner()
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        result = runner.invoke(cli, ["preview", str(sample_notebook_file)])
    # mock returns segments named A-E
    assert "A" in result.output
    assert "E" in result.output


def test_preview_missing_notebook(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["preview", str(tmp_path / "nonexistent.yaml")])
    assert result.exit_code != 0
