"""Outline pass — Pydantic model + jinja rendering. Stage executor in Task 20."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

from gencast.profiles.schemas import Speaker

SegmentSize = Literal["short", "medium", "long"]

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape(default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


class OutlineSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    size: SegmentSize = "medium"


class Outline(BaseModel):
    model_config = ConfigDict(extra="ignore")
    segments: list[OutlineSegment]


def render_outline_prompt(
    *,
    briefing: str,
    content: str,
    speakers: list[Speaker],
    num_segments: int,
    language: str | None,
) -> str:
    template = _jinja_env.get_template("outline.jinja")
    return template.render(
        briefing=briefing,
        content=content,
        speakers=speakers,
        num_segments=num_segments,
        language=language,
    )
