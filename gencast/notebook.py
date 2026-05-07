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
    return Notebook(**data)
