"""
Router – POST /transcribe

Thin HTTP layer: validate → call WhisperService → return JSON.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.transcribe import TranscribeRequest, TranscribeResponse
from app.services.whisper import WhisperService
from app.utils.logger import get_logger

router = APIRouter(prefix="/transcribe", tags=["3 - Transcribe"])
log    = get_logger("router.transcribe")
_svc   = WhisperService()


@router.post(
    "",
    response_model=TranscribeResponse,
    summary="Transcribe video to SRT",
    description=(
        "Extracts audio from the video and generates an SRT subtitle file "
        "using OpenAI Whisper (runs locally). "
        "Available models: tiny | base | small | medium | large."
    ),
)
def transcribe_video(body: TranscribeRequest) -> TranscribeResponse:
    log.info("Transcribe request: %s (model=%s)", body.videoPath, body.model)
    try:
        srt_path = _svc.transcribe(video_path=body.videoPath, model=body.model)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return TranscribeResponse(status="success", srtPath=srt_path)
