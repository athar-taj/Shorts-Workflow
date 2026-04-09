"""
models/schemas.py - Pydantic data models used across the pipeline.
"""

from __future__ import annotations
from pathlib import Path

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class Category(str, Enum):
    KIDS_FUN_STORY = "kids_fun_story"
    HORROR_SHORT = "horror_short"
    MOTIVATIONAL_STORY = "motivational_story"
    COMEDY_SKETCH = "comedy_sketch"


class VoiceType(str, Enum):
    NARRATOR = "narrator"
    CHARACTER = "character"


# ── Scene & Story ──────────────────────────────────────────────────────────────

class Scene(BaseModel):
    """Represents a single scene in a short video."""
    text: str = Field(..., description="Narration text (≤ 24 words)")
    image_prompt: str = Field(..., description="Stable Diffusion prompt for this scene")
    voice: VoiceType = Field(VoiceType.NARRATOR, description="Voice type")
    image_path: Optional[str] = Field(None, description="Local saved image path (populated later)")
    audio_path: Optional[str] = Field(None, description="Local saved audio path (populated later)")


class StoryOutput(BaseModel):
    """JSON structure returned by the story service."""
    title: str = Field(..., description="Short catchy video title")
    scenes: list[Scene] = Field(..., min_length=1, max_length=5)


# ── Memory ─────────────────────────────────────────────────────────────────────

class EpisodeMemory(BaseModel):
    """Persisted memory record for a story series."""
    series_id: str = Field(..., description="Unique identifier for the series")
    category: Category
    chapter: int = Field(1, ge=1)
    summary: str = Field("", description="Running story summary (used for continuation)")
    title: Optional[str] = None


# ── Pipeline Result ────────────────────────────────────────────────────────────

class PipelineResult(BaseModel):
    """Final response returned by the API."""
    video_path: str
    title: str
    category: str
    chapter: int
    youtube_url: Optional[str] = None



