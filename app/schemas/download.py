"""Schemas – Download endpoint."""

from typing import Optional
from pydantic import BaseModel, field_validator


class DownloadRequest(BaseModel):
    videoUrl: str
    quality: Optional[str] = "best"   # "2160p", "1080p", "720p", "best"

    @field_validator("videoUrl")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        if "youtube.com" not in v and "youtu.be" not in v:
            raise ValueError("videoUrl must be a YouTube link.")
        return v


class DownloadResponse(BaseModel):
    status: str
    videoId: str
    filePath: str
    cached: bool
