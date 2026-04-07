"""Schemas – Process (crop + captions) endpoints."""

from typing import Optional
from pydantic import BaseModel


class CropRequest(BaseModel):
    inputPath: str
    durationSec: Optional[int] = None    # None → uses settings default (60 s)
    startSec: Optional[int] = None       # None → uses settings default (0)


class CropResponse(BaseModel):
    status: str
    outputPath: str


class CaptionRequest(BaseModel):
    videoPath: str
    srtPath: str
    headingText: Optional[str] = None    # None → uses settings default


class CaptionResponse(BaseModel):
    status: str
    finalPath: str
    captioned: bool
