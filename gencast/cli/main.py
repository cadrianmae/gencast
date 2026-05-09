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
@click.option("-v", "--verbose", "verbose", is_flag=True, help="Show INFO messages.")
@click.option("-vv", "--debug", "debug", is_flag=True, help="Show DEBUG messages.")
@click.option("-q", "--quiet", "quiet", is_flag=True, help="Spinner only — no INFO/DEBUG.")
@click.option("--silent", "silent", is_flag=True, help="Silent — errors only.")
@click.option(
    "--log-file", "log_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None, help="Tee full DEBUG log to this file regardless of console verbosity.",
)
@click.version_option(__version__, prog_name="gencast")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, debug: bool, quiet: bool, silent: bool, log_file: Path | None) -> None:
    """gencast — generate conversational podcasts from documents."""
    # Mutual-exclusion check
    flag_count = sum([verbose, debug, quiet, silent])
    if flag_count > 1:
        raise click.UsageError(
            "Verbosity flags are mutually exclusive: pick at most one of "
            "-v / -vv / -q / --silent."
        )

    # Resolve verbosity int
    # Ladder: default=1 (normal), -v=2 (verbose), -vv/--debug=3 (debug),
    #         -q/--quiet=0 (warnings+errors), --silent=-1 (errors only).
    if silent:
        verbosity = -1
    elif quiet:
        verbosity = 0
    elif debug:
        verbosity = 3
    elif verbose:
        verbosity = 2
    else:
        verbosity = 1  # default — INFO visible but not extra verbose

    from gencast.logger import make_reporter
    reporter = make_reporter(verbosity=verbosity)
    ctx.ensure_object(dict)
    ctx.obj["reporter"] = reporter
    ctx.obj["log_file"] = log_file

    # Tee full DEBUG log to file regardless of console verbosity.
    if log_file is not None:
        import logging
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        ctx.obj["_log_file_handler"] = file_handler
        # Emit a startup record so the file is never empty after a successful run.
        logging.getLogger("gencast").debug("gencast session started (log-file tee active)")


@cli.command("list-profiles")
@click.option(
    "--type",
    "kind",
    type=click.Choice(["speakers", "episodes", "rooms", "all"], case_sensitive=False),
    default="all",
    help="Which profile kind to list.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON array.")
def list_profiles(kind: str, as_json: bool) -> None:
    """List available profiles from the 3-level cascade (project, user, bundled)."""
    import json as _json

    kinds = ["speakers", "episodes", "rooms"] if kind == "all" else [kind]

    if as_json:
        from gencast.profiles.loader import load_profile
        rows: list[dict[str, object]] = []
        for k in kinds:
            names = list_profile_names(k)  # type: ignore[arg-type]
            for name in names:
                try:
                    profile = load_profile(k, name)  # type: ignore[arg-type]
                    description = getattr(profile, "description", None)
                except Exception:
                    description = None
                try:
                    orig = origin_marker(k, name)  # type: ignore[arg-type]
                except ProfileNotFoundError:
                    orig = "?"
                rows.append({"kind": k, "name": name, "description": description, "origin": orig})
        click.echo(_json.dumps(rows, indent=2))
        return

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
@click.pass_context
def generate(ctx: click.Context, notebook_path: Path) -> None:
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

    reporter = ctx.obj["reporter"]
    state = run_pipeline(nb, reporter=reporter)

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


@cli.command("subtitle")
@click.argument("audio_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out", "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None, help="Output SRT path (default: same dir + .srt).",
)
def subtitle(audio_path: Path, out_path: Path | None) -> None:
    """Re-subtitle an external audio file via Whisper."""
    from gencast.pipeline.whisper_subtitle import transcribe_to_srt
    srt_content = transcribe_to_srt(audio_path)
    if out_path is None:
        out_path = audio_path.with_suffix(".srt")
    out_path.write_text(srt_content)
    click.secho(f"Wrote {out_path}", fg="green")


@cli.command("estimate")
@click.argument("notebook_path", required=False,
                type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True,
              help="Emit machine-readable JSON instead of a table.")
@click.option("--no-suggestions", is_flag=True,
              help="Skip cheaper-model suggestions in human output.")
@click.option("--rates-only", is_flag=True,
              help="Dump the model-rate table only (no notebook required).")
@click.option("--provider", "provider_filter", default=None,
              help="Filter --rates-only to one provider (e.g. anthropic, openai, ollama).")
@click.option("--all-models", is_flag=True,
              help="With --rates-only: include every model LiteLLM knows (~2,700), not just bundled defaults.")
def estimate(notebook_path: Path | None, as_json: bool, no_suggestions: bool,
             rates_only: bool, provider_filter: str | None, all_models: bool) -> None:
    """Predict USD cost for a notebook before running the pipeline."""
    from gencast.pipeline.estimate import dump_rates_table, estimate_notebook
    from gencast.cli.estimate_formatter import (
        format_json, format_rates_json, format_rates_table, format_table,
    )

    if rates_only:
        rates = dump_rates_table(provider_filter=provider_filter, all_models=all_models)
        click.echo(format_rates_json(rates) if as_json else format_rates_table(rates))
        return

    if notebook_path is None:
        raise click.UsageError("NOTEBOOK_PATH is required unless --rates-only is set.")

    from gencast.notebook import load_notebook
    nb = load_notebook(notebook_path)
    est = estimate_notebook(nb)

    if as_json:
        click.echo(format_json(est))
        return

    if no_suggestions:
        # Strip suggestions before formatting (Estimate is frozen, so rebuild)
        from gencast.pipeline.estimate import Estimate
        est = Estimate(
            notebook_path=est.notebook_path,
            source_tokens=est.source_tokens,
            stages=est.stages,
            total_usd=est.total_usd,
            uncertainty_pct=est.uncertainty_pct,
            suggestions=[],
        )
    click.echo(format_table(est))


@cli.group("cache")
def cache_group() -> None:
    """Inspect and clear gencast caches."""


def _cache_dirs(kind: str) -> list[Path]:
    """Resolve cache directories for the given kind (tts | llm | extract | all)."""
    import os
    base = Path(os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")) / "gencast"
    if kind == "all":
        return [base / "tts", base / "llm", base / "extract"]
    return [base / kind]


def _du(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


@cache_group.command("status")
@click.option(
    "--type", "kind",
    type=click.Choice(["tts", "llm", "extract", "all"]),
    default="all",
)
def cache_status(kind: str) -> None:
    """Print cache size and path for each cache kind."""
    for d in _cache_dirs(kind):
        size = _du(d)
        click.echo(f"  {d.name:10s} {_format_bytes(size):>12}  {d}")


@cache_group.command("clear")
@click.option(
    "--type", "kind",
    type=click.Choice(["tts", "llm", "extract", "all"]),
    default="all",
)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def cache_clear(kind: str, yes: bool) -> None:
    """Remove cache contents (preserves directory)."""
    targets = _cache_dirs(kind)
    total = sum(_du(d) for d in targets)
    if not yes:
        click.confirm(
            f"Remove {_format_bytes(total)} from {len(targets)} cache(s)?",
            abort=True,
        )
    for d in targets:
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file():
                    f.unlink()
    click.secho(f"Cleared {_format_bytes(total)}", fg="green")
