from click.testing import CliRunner
from gencast.cli.main import cli


def test_cli_help():
    """Top-level --help shows list-profiles subcommand."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "list-profiles" in result.output


def test_list_profiles_default_lists_all_kinds():
    """list-profiles with no --type lists speakers, episodes, rooms sections."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles"])
    assert result.exit_code == 0
    # Three kind-headers should appear regardless of whether YAMLs exist
    for kind in ["speakers", "episodes", "rooms"]:
        assert kind in result.output


def test_list_profiles_filtered_by_type():
    """--type rooms shows only the rooms section."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles", "--type", "rooms"])
    assert result.exit_code == 0
    assert "rooms" in result.output
    # speakers/episodes headers should NOT appear
    assert "speakers:" not in result.output
    assert "episodes:" not in result.output


def test_list_profiles_invalid_type():
    """Unknown --type value is rejected."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles", "--type", "invalid"])
    assert result.exit_code != 0


def test_cli_version():
    """--version prints the gencast version string."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "gencast" in result.output
