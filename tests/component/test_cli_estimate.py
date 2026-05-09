import json
from click.testing import CliRunner

from gencast.cli.main import cli


def test_cli_estimate_table():
    runner = CliRunner()
    result = runner.invoke(cli, ["estimate", "tests/fixtures/notebooks/smoke.yaml"])
    assert result.exit_code == 0, result.output
    assert "Total:" in result.output
    assert "±25%" in result.output
    # USD amount somewhere
    assert "$" in result.output


def test_cli_estimate_json():
    runner = CliRunner()
    result = runner.invoke(cli,
        ["estimate", "tests/fixtures/notebooks/smoke.yaml", "--json"]
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert "stages" in parsed
    assert "total_usd" in parsed
    assert "uncertainty_pct" in parsed


def test_cli_estimate_no_suggestions_flag_omits_block():
    runner = CliRunner()
    result = runner.invoke(cli,
        ["estimate", "tests/fixtures/notebooks/smoke.yaml", "--no-suggestions"]
    )
    assert result.exit_code == 0
    assert "Cheaper alternatives" not in result.output


def test_cli_estimate_rates_only_table():
    runner = CliRunner()
    result = runner.invoke(cli, ["estimate", "--rates-only"])
    assert result.exit_code == 0, result.output
    assert "input/1k" in result.output.lower()
    assert "claude" in result.output  # at least one bundled model present


def test_cli_estimate_rates_only_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["estimate", "--rates-only", "--json"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)
    assert any("/" in k for k in parsed.keys())


def test_cli_estimate_rates_only_provider_filter():
    runner = CliRunner()
    result = runner.invoke(cli,
        ["estimate", "--rates-only", "--provider", "anthropic", "--json"]
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert all(k.startswith("anthropic/") for k in parsed.keys())


def test_cli_estimate_rates_only_all_models():
    runner = CliRunner()
    defaults = json.loads(
        runner.invoke(cli, ["estimate", "--rates-only", "--json"]).output
    )
    everything = json.loads(
        runner.invoke(cli, ["estimate", "--rates-only", "--all-models", "--json"]).output
    )
    assert len(everything) > len(defaults)


def test_cli_estimate_missing_notebook_errors_cleanly():
    runner = CliRunner()
    result = runner.invoke(cli, ["estimate"])
    # No notebook + no --rates-only → usage error
    assert result.exit_code != 0
