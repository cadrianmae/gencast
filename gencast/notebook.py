"""Notebook YAML schema + loader."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

OutputFormat = Literal["m4a", "mp3", "transcript", "outline", "cost"]


class NotebookOutput(BaseModel):
    """Where + which formats to write."""
    model_config = ConfigDict(extra="forbid")

    dir: Path = Path("./out")
    basename: str | None = None
    formats: list[OutputFormat] = Field(default_factory=lambda: ["m4a"])


class NotebookOverrides(BaseModel):
    """Optional per-notebook overrides on top of episode-profile defaults."""
    model_config = ConfigDict(extra="forbid")

    outline_provider: str | None = None
    outline_model: str | None = None
    transcript_provider: str | None = None
    transcript_model: str | None = None
    num_segments: int | None = None
    briefing_suffix: str | None = None
    briefing: str | None = None  # full replacement


class Notebook(BaseModel):
    """Top-level notebook YAML — composes speaker + episode + room profiles."""
    model_config = ConfigDict(extra="forbid")  # strict for notebook YAML

    title: str = Field(..., min_length=1)
    description: str | None = None
    tags: list[str] | None = None

    output: NotebookOutput = Field(default_factory=NotebookOutput)
    sources: list[str]
    speaker_profile: str = "educational-duo"
    episode_profile: str = "concept-explainer"
    room_profile: str = "small-room"
    overrides: NotebookOverrides = Field(default_factory=NotebookOverrides)

    @field_validator("sources")
    @classmethod
    def at_least_one_source(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Notebook needs at least one source")
        return v


def load_notebook(path: str | Path) -> Notebook:
    """Load + validate a notebook YAML file."""
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    nb = Notebook(**data)
    # Attach source path so estimate/reporting can display a meaningful file name.
    # object.__setattr__ bypasses Pydantic's frozen/strict mode.
    object.__setattr__(nb, "_source_path", path)
    return nb


import re
from dataclasses import dataclass

from .profiles.loader import load_profile
from .profiles.schemas import EpisodeProfile, RoomProfile, SpeakerProfile


@dataclass
class ResolvedNotebook:
    """Notebook with all profiles loaded and overrides applied — what the pipeline reads."""
    notebook: Notebook
    speaker: SpeakerProfile
    episode: EpisodeProfile
    room: RoomProfile

    # Resolved fields
    briefing: str
    outline_provider: str
    outline_model: str
    transcript_provider: str
    transcript_model: str
    num_segments: int
    basename: str


def _slugify(s: str) -> str:
    """Convert a title to a filesystem-friendly basename."""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")


def resolve_notebook(nb: Notebook) -> ResolvedNotebook:
    """Load profiles, apply overrides, return a fully-resolved view of the notebook."""
    speaker = load_profile("speakers", nb.speaker_profile)
    episode = load_profile("episodes", nb.episode_profile)
    room = load_profile("rooms", nb.room_profile)

    # Briefing resolution: full replacement > base + suffix > base
    if nb.overrides.briefing is not None:
        briefing = nb.overrides.briefing
    elif nb.overrides.briefing_suffix is not None:
        briefing = f"{episode.default_briefing}\n\nAdditional focus: {nb.overrides.briefing_suffix}"
    else:
        briefing = episode.default_briefing

    return ResolvedNotebook(
        notebook=nb,
        speaker=speaker,
        episode=episode,
        room=room,
        briefing=briefing,
        outline_provider=nb.overrides.outline_provider or episode.outline_provider,
        outline_model=nb.overrides.outline_model or episode.outline_model,
        transcript_provider=nb.overrides.transcript_provider or episode.transcript_provider,
        transcript_model=nb.overrides.transcript_model or episode.transcript_model,
        num_segments=nb.overrides.num_segments or episode.num_segments,
        basename=nb.output.basename or _slugify(nb.title),
    )
