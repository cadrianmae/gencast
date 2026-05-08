"""Outline pass — Pydantic model + jinja rendering. Stage executor in Task 20."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from gencast.logger import Reporter

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

from gencast.cost import CostMeter
from gencast.llm import chat_completion
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


# Strip optional ```json ... ``` code fences from LLM output.
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_code_fence(s: str) -> str:
    m = _FENCE_RE.match(s)
    return m.group(1) if m else s


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


def run_outline_stage(
    *,
    briefing: str,
    content: str,
    speakers: list[Speaker],
    num_segments: int,
    language: str | None,
    outline_provider: str,
    outline_model: str,
    cost_meter: CostMeter,
    reporter: "Reporter | None" = None,
) -> Outline:
    """Generate the podcast outline. One LLM call, JSON-structured output."""
    if reporter is not None:
        reporter.stage_start(5, 10, "Outline")
        reporter.stage_activity(
            f"[{outline_provider}/{outline_model}] generating {num_segments} segments"
        )

    prompt = render_outline_prompt(
        briefing=briefing, content=content, speakers=speakers,
        num_segments=num_segments, language=language,
    )
    response = chat_completion(
        provider=outline_provider,
        model=outline_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=3000,
        cost_meter=cost_meter,
        stage="outline",
    )

    raw = _strip_code_fence(response.content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Outline LLM response was not valid JSON: {e}. Raw response: {raw[:300]!r}"
        ) from e

    if reporter is not None:
        reporter.stage_done()

    return Outline(**data)
