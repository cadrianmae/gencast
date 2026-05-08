"""gencast CLI entry point."""

from __future__ import annotations

from pathlib import Path

import click

from gencast import __version__
from gencast.notebook import load_notebook
from gencast.pipeline import run_pipeline, run_through_outline
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


@cli.command("preview")
@click.argument("notebook_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def preview(notebook_path: Path) -> None:
    """Render outline only — fast dry-run before paying for full transcript + audio generation."""
    nb = load_notebook(notebook_path)
    state = run_through_outline(nb)
    assert state.outline is not None, "outline should be populated after run_through_outline"

    click.secho(f"\n{state.notebook.title}", fg="cyan", bold=True)
    click.echo(f"  speakers:  {state.resolved.speaker.name}")
    click.echo(f"  episode:   {state.resolved.episode.name}")
    click.echo(f"  room:      {state.resolved.room.name}")
    click.echo(f"  source:    {state.source_tokens_original:,} tokens")
    click.echo(f"  cost so far: ${state.cost.total_usd:.4f}")

    click.secho(f"\nOutline ({len(state.outline.segments)} segments):", fg="green")
    for i, seg in enumerate(state.outline.segments, 1):
        click.echo(f"  {i}. [{seg.size}] {seg.name}")
        for line in seg.description.split("\n"):
            click.echo(f"       {line}")


@cli.command("init")
@click.option("--minimal", is_flag=True, help="Skip optional prompts.")
@click.option(
    "--copy", "copy_from",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None, help="Pre-fill from an existing notebook YAML.",
)
@click.option(
    "--out", "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("notebook.yaml"),
    help="Where to write the notebook YAML (default: ./notebook.yaml).",
)
def init(minimal: bool, copy_from: Path | None, output_path: Path) -> None:
    """Interactively create a notebook YAML."""
    from gencast.cli.init_wizard import run_wizard
    run_wizard(output_path=output_path, minimal=minimal, copy_from=copy_from)


@cli.command("generate")
@click.argument("notebook_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def generate(notebook_path: Path) -> None:
    """Run the full pipeline: extract → outline → transcript → audio → package."""
    nb = load_notebook(notebook_path)

    # Resolve output.dir relative to notebook file location if it's relative
    if not nb.output.dir.is_absolute():
        nb.output.dir = (notebook_path.parent / nb.output.dir).resolve()

    # Resolve source paths relative to the notebook's parent directory
    nb.sources = [
        str((notebook_path.parent / s).resolve()) if not Path(s).is_absolute() else s
        for s in nb.sources
    ]

    state = run_pipeline(nb)

    click.secho(f"\n{state.notebook.title}", fg="cyan", bold=True)
    click.echo(f"  speakers:   {state.resolved.speaker.name}")
    click.echo(f"  episode:    {state.resolved.episode.name}")
    click.echo(f"  room:       {state.resolved.room.name}")
    click.echo(f"  source:     {state.source_tokens_original:,} tokens")
    click.echo(f"  outline:    {len(state.outline.segments) if state.outline else 0} segments")
    click.echo(f"  transcript: {len(state.transcript.turns) if state.transcript else 0} turns")
    click.echo(f"  audio:      {len(state.clips)} clips, "
               f"{(len(state.combined_audio) // 1000) if state.combined_audio else 0}s combined")
    click.echo(f"  cost:       ${state.cost.total_usd:.4f}")
    click.secho(f"\nWrote outputs to {nb.output.dir}", fg="green")
