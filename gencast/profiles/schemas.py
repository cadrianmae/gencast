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


class SpeakerProfile(BaseModel):
    """A named collection of 1-4 speakers sharing a TTS provider."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    description: str | None = None
    tts_provider: str = Field(..., min_length=1)
    tts_model: str = Field(..., min_length=1)
    tts_config: dict[str, Any] | None = None
    speakers: list[Speaker]

    @field_validator("speakers")
    @classmethod
    def validate_speakers(cls, v: list[Speaker]) -> list[Speaker]:
        if not 1 <= len(v) <= 4:
            raise ValueError(f"Must have 1-4 speakers, got {len(v)}")
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            raise ValueError("Speaker names must be unique within a profile")
        voices = [s.voice_id for s in v]
        if len(voices) != len(set(voices)):
            raise ValueError("Voice IDs must be unique within a profile")
        return v


SegmentSize = Literal["short", "medium", "long"]


class EpisodeProfile(BaseModel):
    """How the podcast is structured — briefing, segment count, models per stage."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    description: str | None = None
    speaker_profile: str | None = None
    default_briefing: str = Field(..., min_length=1)
    num_segments: int = 6
    segment_size_default: SegmentSize = "medium"
    outline_provider: str = "anthropic"
    outline_model: str = "claude-haiku-4-5"
    transcript_provider: str = "anthropic"
    transcript_model: str = "claude-sonnet-4-5"
    outline_config: dict[str, Any] | None = None
    transcript_config: dict[str, Any] | None = None
    summarize_provider: str | None = None
    summarize_model: str | None = None
    language: str | None = None

    @field_validator("num_segments")
    @classmethod
    def validate_num_segments(cls, v: int) -> int:
        if not 3 <= v <= 10:
            raise ValueError(f"num_segments must be 3-10, got {v}")
        return v


class RoomProfile(BaseModel):
    """Spatial audio + ambience configuration."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    description: str | None = None
    arc_deg: float = Field(120.0, ge=0.0, le=180.0)
    itd_max_ms: float = Field(0.6, ge=0.0)
    jitter_deg: float = Field(1.5, ge=0.0)
    reverb_t60_s: float = Field(0.30, ge=0.0)
    reverb_wet: float = Field(0.05, ge=0.0, le=1.0)
    reverb_lpf_hz: float = Field(2000.0, gt=0.0)
    reverb_damping: float = Field(0.55, ge=0.0, le=1.0)
    predelay_ms: float = Field(20.0, ge=0.0)
    table_radius_m: float = Field(0.85, gt=0.0)
    ambience_db: float | None = -70.0
    ambience_lpf_hz: float = Field(1500.0, gt=0.0)
    ambience_fan_rumble_db: float = 4.0
    target_dbfs: float = Field(-1.0, le=0.0)
