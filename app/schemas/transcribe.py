"""Schemas – Transcribe endpoint."""

from typing import Optional
from pydantic import BaseModel


VALID_MODELS = {"tiny", "base", "small", "medium", "large"}


class TranscribeRequest(BaseModel):
    videoPath: str
    model: Optional[str] = None    # None → uses settings default ("base")


class TranscribeResponse(BaseModel):
    status: str
    srtPath: str
