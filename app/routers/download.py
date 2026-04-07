"""
Router – POST /download

Thin HTTP layer: validate input → call DownloadService → format response.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.download import DownloadRequest, DownloadResponse
from app.services.downloader import DownloadService
from app.utils.logger import get_logger

router = APIRouter(prefix="/download", tags=["1 - Download"])
log    = get_logger("router.download")
_svc   = DownloadService()


@router.post(
    "",
    response_model=DownloadResponse,
    summary="Download a YouTube video",
    description=(
        "Downloads a YouTube video using yt-dlp and saves it to the server's "
        "temp directory. Returns the local file path."
    ),
)
def download_video(body: DownloadRequest) -> DownloadResponse:
    log.info("Download request: %s (quality: %s)", body.videoUrl, body.quality)
    try:
        result = _svc.download(body.videoUrl, quality=body.quality)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return DownloadResponse(status="success", **result)
