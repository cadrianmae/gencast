"""gencast CLI entry point."""

from __future__ import annotations

import click

from gencast import __version__
from gencast.profiles.loader import (
    ProfileNotFoundError,
    list_profile_names,
    origin_marker,
)


@click.group(invoke_without_command=False)
@click.version_option(__version__, prog_name="gencast")
def cli() -> None:
    """gencast — generate conversational podcasts from documents."""


@cli.command("list-profiles")
@click.option(
    "--type",
    "kind",
    type=click.Choice(["speakers", "episodes", "rooms", "all"], case_sensitive=False),
    default="all",
    help="Which profile kind to list.",
)
def list_profiles(kind: str) -> None:
    """List available profiles from the 3-level cascade (project, user, bundled)."""
    kinds = ["speakers", "episodes", "rooms"] if kind == "all" else [kind]
    for k in kinds:
        click.secho(f"\n{k}:", fg="cyan", bold=True)
        names = list_profile_names(k)  # type: ignore[arg-type]
        if not names:
            click.echo("  (none found)")
            continue
        for name in names:
            try:
                origin = origin_marker(k, name)  # type: ignore[arg-type]
            except ProfileNotFoundError:
                origin = "?"
            click.echo(f"  {name:30s} ({origin})")
