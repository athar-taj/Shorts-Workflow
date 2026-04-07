"""Schemas – Orchestrator endpoint."""

from typing import Optional
from pydantic import BaseModel, field_validator


class OrchestratorRequest(BaseModel):
    videoUrl: str
    durationSec: Optional[int] = None
    startSec: Optional[int] = None
    whisperModel: Optional[str] = None
    videoQuality: Optional[str] = "best"
    headingText: Optional[str] = None    # None -> uses settings default


    @field_validator("videoUrl")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        if "youtube.com" not in v and "youtu.be" not in v:
            raise ValueError("videoUrl must be a YouTube link.")
        return v


class StepLog(BaseModel):
    step: str
    result: dict


class OrchestratorResponse(BaseModel):
    status: str
    videoId: str
    finalVideoPath: str
    steps: list[StepLog]
