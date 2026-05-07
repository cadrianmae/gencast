"""Pydantic schemas for speakers, episodes, rooms, profiles."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Avatar(BaseModel):
    """Speaker avatar — emoji for terminals, ASCII or image for richer renderers."""
    model_config = ConfigDict(extra="ignore")

    emoji: str | None = None
    ascii: str | None = None     # path relative to profile dir
    image: str | None = None     # path relative to profile dir
    color: str | None = None     # hex like "#ff7847"


class Speaker(BaseModel):
    """A single host/voice."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    voice_id: str = Field(..., min_length=1)
    backstory: str = Field(..., min_length=1)
    personality: str = Field(..., min_length=1)
    avatar: Avatar | None = None
    tts_provider: str | None = None
    tts_model: str | None = None
    tts_config: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty after stripping")
        return v
