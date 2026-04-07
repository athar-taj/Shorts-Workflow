"""
Router – POST /process/crop  &  POST /process/captions

Thin HTTP layer: validate → call FFmpegService → return JSON.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.process import (
    CaptionRequest, CaptionResponse,
    CropRequest, CropResponse,
)
from app.services.ffmpeg import FFmpegService
from app.utils.logger import get_logger

router = APIRouter(prefix="/process", tags=["2 - Process"])
log    = get_logger("router.process")
_svc   = FFmpegService()


@router.post(
    "/crop",
    response_model=CropResponse,
    summary="Crop video to vertical 9:16",
    description=(
        "Converts a horizontal video to vertical (9:16) by center-cropping "
        "and trims it to the requested duration."
    ),
)
def crop_video(body: CropRequest) -> CropResponse:
    log.info("Crop request: %s (duration=%s, start=%s)", body.inputPath, body.durationSec, body.startSec)
    try:
        output_path = _svc.crop_to_vertical(
            input_path=body.inputPath,
            duration_sec=body.durationSec,
            start_sec=body.startSec,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return CropResponse(status="success", outputPath=output_path)


@router.post(
    "/captions",
    response_model=CaptionResponse,
    summary="Burn SRT subtitles into video",
    description=(
        "Burns subtitles from an SRT file into the video using FFmpeg. "
        "If the SRT file is missing the original video is returned as-is "
        "with captioned=false."
    ),
)
def burn_captions(body: CaptionRequest) -> CaptionResponse:
    log.info("Caption burn request: video=%s srt=%s", body.videoPath, body.srtPath)
    try:
        final_path, captioned = _svc.burn_captions(
            video_path=body.videoPath,
            srt_path=body.srtPath,
            heading_text=body.headingText,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return CaptionResponse(status="success", finalPath=final_path, captioned=captioned)
