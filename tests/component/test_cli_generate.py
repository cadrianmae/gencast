"""End-to-end CLI smoke for `gencast generate`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gencast.cli.main import cli


@pytest.fixture
def smoke_notebook_dir(tmp_path):
    """Copy fixtures into a temp dir + rewrite source path to be local."""
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "notebooks"
    src_md = (fixture_dir / "smoke_source.md").read_text()
    nb_yaml = (fixture_dir / "smoke.yaml").read_text()
    (tmp_path / "smoke_source.md").write_text(src_md)
    nb_path = tmp_path / "smoke.yaml"
    nb_path.write_text(nb_yaml)
    return nb_path


class _FastBackend:
    backend_name = "stub"
    model = "stub-1"
    usd_per_audio_second = 0.0

    async def synthesize(self, *, voice, text):
        from pydub import AudioSegment
        import io
        seg = AudioSegment.silent(duration=80, frame_rate=24000).set_channels(1)
        buf = io.BytesIO()
        seg.export(buf, format="mp3", bitrate="64k")
        return buf.getvalue(), 0.08


def _llm(content):
    r = MagicMock()
    r.content = content
    return r


def test_generate_smoke_runs_end_to_end(smoke_notebook_dir, tmp_path):
    outline_json = (
        '{"segments":['
        '{"name":"Intro","description":"d","size":"short"},'
        '{"name":"Body","description":"d","size":"short"},'
        '{"name":"Wrap","description":"d","size":"short"}'
        ']}'
    )
    seg_json = '{"turns":[{"speaker":"Sophie","text":"Hi."},{"speaker":"Ben","text":"Bye."}]}'

    runner = CliRunner()
    with patch("gencast.pipeline.outline.chat_completion") as mock_ol, \
         patch("gencast.pipeline.transcript.chat_completion") as mock_tx, \
         patch("gencast.pipeline.get_default_tts_backend") as mock_tts:
        mock_ol.return_value = _llm(outline_json)
        mock_tx.return_value = _llm(seg_json)
        mock_tts.return_value = _FastBackend()

        # Notebook output.dir is relative; chdir so it lands in tmp_path
        result = runner.invoke(
            cli, ["generate", str(smoke_notebook_dir)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    # Output directory ./out is relative to cwd, which CliRunner doesn't change.
    # The notebook's NotebookOutput.dir resolves relative to the YAML's parent.
    # We assert on output via the printed summary.
    assert "Wrote outputs to" in result.output
