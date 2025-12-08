"""
Pydantic models for structured podcast generation.
"""
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field, field_validator, model_validator


class DialogueSegment(BaseModel):
    """Single dialogue segment from one host."""
    speaker: Literal["HOST1", "HOST2"] = Field(
        description="The speaker (HOST1 or HOST2)"
    )
    text: str = Field(
        description="The dialogue text spoken by this host"
    )

    @field_validator('text')
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        # Only validate if value is present (allows streaming with Partial[Model])
        if v and not v.strip():
            raise ValueError("Dialogue text cannot be empty")
        return v.strip() if v else v


class PodcastDialogue(BaseModel):
    """Complete podcast dialogue with all segments."""
    segments: List[DialogueSegment] = Field(
        description="List of dialogue segments"
    )

    @model_validator(mode='after')
    def validate_complete_dialogue(self) -> 'PodcastDialogue':
        """Validate dialogue is complete (only runs on finalized models, not during streaming)."""
        # Only validate if we have actual segments (skip during streaming when list might be empty)
        if self.segments and len(self.segments) >= 2:
            speakers = {seg.speaker for seg in self.segments if seg.speaker}
            if speakers and len(speakers) < 2:
                raise ValueError("Both HOST1 and HOST2 must speak")
        return self

    def to_text_format(self) -> str:
        """Convert to legacy text format for audio.py."""
        return '\n'.join(
            f"{seg.speaker}: {seg.text}"
            for seg in self.segments
        )

    def count_segments(self) -> Dict[str, int]:
        """Count segments per speaker."""
        counts: Dict[str, int] = {"HOST1": 0, "HOST2": 0}
        for seg in self.segments:
            counts[seg.speaker] += 1
        return counts


class PlanTopic(BaseModel):
    """Single topic in podcast plan."""
    title: str
    key_points: List[str]
    estimated_minutes: Optional[float] = Field(None, ge=0.5)

    @model_validator(mode='after')
    def validate_complete_topic(self) -> 'PlanTopic':
        """Validate topic is complete (only runs on finalized models, not during streaming)."""
        # Only validate if fields have actual content (skip during streaming)
        if self.title and len(self.title) < 1:
            raise ValueError("Topic title must have at least 1 character")
        if self.key_points and len(self.key_points) < 1:
            raise ValueError("Topic must have at least 1 key point")
        return self


class PodcastPlan(BaseModel):
    """Structured podcast plan."""
    overview: str
    topics: List[PlanTopic]
    target_audience: str
    estimated_total_minutes: Optional[float] = Field(None, ge=1.0)
    coverage_notes: Optional[str] = None

    @model_validator(mode='after')
    def validate_complete_plan(self) -> 'PodcastPlan':
        """Validate plan is complete (only runs on finalized models, not during streaming)."""
        # Only validate if fields have meaningful content (skip during streaming when fields are empty)
        if self.overview and len(self.overview) < 10:
            raise ValueError("Plan overview must have at least 10 characters")
        if self.topics and len(self.topics) < 1:
            raise ValueError("Plan must have at least 1 topic")
        return self

    def to_markdown(self) -> str:
        """Convert to markdown for display."""
        lines = [
            "# Podcast Plan",
            "",
            f"**Overview:** {self.overview}",
            "",
            f"**Target Audience:** {self.target_audience}",
            ""
        ]

        if self.estimated_total_minutes:
            lines.extend([
                f"**Estimated Duration:** {self.estimated_total_minutes:.1f} minutes",
                ""
            ])

        lines.append("## Topics")
        lines.append("")

        for i, topic in enumerate(self.topics, 1):
            lines.append(f"### {i}. {topic.title}")
            if topic.estimated_minutes:
                lines.append(f"*Duration: ~{topic.estimated_minutes:.1f} min*")
            lines.append("")
            lines.append("**Key Points:**")
            for point in topic.key_points:
                lines.append(f"- {point}")
            lines.append("")

        if self.coverage_notes:
            lines.extend([
                "## Coverage Notes",
                "",
                self.coverage_notes,
                ""
            ])

        return '\n'.join(lines)
