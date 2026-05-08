"""gencast init wizard — prompts user, emits notebook.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import click
import yaml

from gencast.profiles.loader import list_profile_names

ProfileKind = Literal["speakers", "episodes", "rooms"]


def _pick_profile(kind: ProfileKind, default_idx: int = 1) -> str:
    """Show a numbered list and prompt for an index. Returns the chosen profile name."""
    names = list_profile_names(kind)
    if not names:
        raise click.UsageError(f"No {kind} profiles found in cascade")
    click.echo(f"\nAvailable {kind} profiles:")
    for i, name in enumerate(names, start=1):
        click.echo(f"  {i}. {name}")
    pick = click.prompt(
        f"Pick {kind[:-1]} profile",
        type=click.IntRange(1, len(names)),
        default=default_idx,
    )
    return names[pick - 1]


def _collect_sources() -> list[str]:
    """Prompt for source paths until a blank line."""
    sources: list[str] = []
    click.echo("\nEnter source paths (one per line, blank line to finish):")
    while True:
        path = click.prompt("Source", default="", show_default=False)
        if not path:
            break
        sources.append(path)
    if not sources:
        raise click.UsageError("Need at least one source")
    return sources


def run_wizard(*, output_path: Path, minimal: bool, copy_from: Path | None) -> None:
    """Run the wizard interactively and write notebook.yaml to output_path."""
    if output_path.exists():
        raise click.UsageError(
            f"{output_path} already exists; remove it or use --copy to seed from it"
        )

    # Pre-fill from existing notebook if --copy
    seed: dict = {}
    if copy_from is not None:
        with copy_from.open() as f:
            seed = yaml.safe_load(f) or {}

    title = click.prompt("Notebook title", default=seed.get("title", "Untitled"))
    sources = _collect_sources() if not seed.get("sources") else seed["sources"]

    speaker_profile = _pick_profile("speakers", default_idx=1)
    episode_profile = _pick_profile("episodes", default_idx=1)
    room_profile = _pick_profile("rooms", default_idx=1)

    formats_raw = click.prompt(
        "Output formats (comma-separated; m4a, mp3, transcript, outline, cost)",
        default="m4a",
    )
    formats = [f.strip() for f in formats_raw.split(",") if f.strip()]

    briefing_suffix = "" if minimal else click.prompt(
        "Briefing suffix (optional, hit enter to skip)",
        default="", show_default=False,
    )

    notebook_dict = {
        "title": title,
        "sources": sources,
        "speaker_profile": speaker_profile,
        "episode_profile": episode_profile,
        "room_profile": room_profile,
        "output": {"dir": "./out", "formats": formats},
    }
    if briefing_suffix:
        notebook_dict["overrides"] = {"briefing_suffix": briefing_suffix}

    output_path.write_text(yaml.safe_dump(notebook_dict, sort_keys=False))
    click.secho(f"\nWrote {output_path}", fg="green")
