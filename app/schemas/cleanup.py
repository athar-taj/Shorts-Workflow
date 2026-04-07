"""Schemas – Cleanup endpoint."""

from pydantic import BaseModel


class CleanupRequest(BaseModel):
    videoId: str


class CleanupResponse(BaseModel):
    status: str
    videoId: str
    deleted: list[str]
    failed: list[dict]
