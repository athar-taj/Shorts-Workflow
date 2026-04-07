"""Schemas – Workflow endpoints."""

from typing import Optional
from pydantic import BaseModel


class TrendingVideoItem(BaseModel):
    videoId: str
    title: str
    channelTitle: str
    viewCount: str
    likeCount: str
    duration: str
    publishedAt: str
    tags: str
    videoUrl: str


class WorkflowAutoRequest(BaseModel):
    # If videoUrl is provided, it skips the trending fetch and just uses this video
    videoUrl: Optional[str] = None
    durationSec: Optional[int] = 60
    startSec: Optional[int] = 0
    videoQuality: Optional[str] = "1080p"
    whisperModel: Optional[str] = "base"


class WorkflowAutoResponse(BaseModel):
    status: str
    videoId: str
    finalVideoPath: str
    metadata: dict
