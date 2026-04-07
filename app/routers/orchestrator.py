"""
Router – POST /generate-short

Orchestrator: runs the full pipeline in a single HTTP call.
  1. Download (yt-dlp)
  2. Crop (FFmpeg → 9:16)
  3. Transcribe (Whisper)  — non-fatal; pipeline continues if this fails
  4. Burn captions (FFmpeg)
"""

from fastapi import APIRouter, HTTPException

from app.schemas.orchestrator import OrchestratorRequest, OrchestratorResponse, StepLog
from app.services.downloader import DownloadService
from app.services.ffmpeg import FFmpegService
from app.services.whisper import WhisperService
from app.utils.file_utils import extract_video_id
from app.utils.logger import get_logger

router = APIRouter(prefix="/generate-short", tags=["5 - Orchestrator"])
log    = get_logger("router.orchestrator")

_downloader = DownloadService()
_ffmpeg     = FFmpegService()
_whisper    = WhisperService()


@router.post(
    "",
    response_model=OrchestratorResponse,
    summary="Run the full pipeline in one call",
    description=(
        "Sequentially runs: Download → Crop (9:16) → Transcribe → Burn Captions. "
        "Transcription failure is non-fatal; the video is returned without captions. "
        "Ideal as a single n8n HTTP Request node."
    ),
)
def generate_short(body: OrchestratorRequest) -> OrchestratorResponse:
    log.info("Orchestrator started for: %s", body.videoUrl)
    steps: list[StepLog] = []

    def record(step_name: str, result: dict) -> dict:
        log.info("[ORCHESTRATOR] %s → %s", step_name, result)
        steps.append(StepLog(step=step_name, result=result))
        return result

    # ── 1. Extract video ID ───────────────────────────────────────────────────
    try:
        video_id = extract_video_id(body.videoUrl)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # ── 2. Download ───────────────────────────────────────────────────────────
    try:
        dl = _downloader.download(body.videoUrl, quality=body.videoQuality)
        record("download", dl)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=f"Download failed: {exc}")

    # ── 3. Crop ───────────────────────────────────────────────────────────────
    try:
        cropped_path = _ffmpeg.crop_to_vertical(
            input_path=dl["filePath"],
            duration_sec=body.durationSec,
            start_sec=body.startSec,
        )
        record("crop", {"outputPath": cropped_path})
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=f"Crop failed: {exc}")

    # ── 4. Transcribe (non-fatal) ─────────────────────────────────────────────
    srt_path: str | None = None
    try:
        srt_path = _whisper.transcribe(video_path=cropped_path, model=body.whisperModel)
        record("transcribe", {"srtPath": srt_path})
    except Exception as exc:  # noqa: BLE001 – intentionally broad; transcription is optional
        log.warning("Transcription skipped (non-fatal): %s", exc)
        record("transcribe", {"warning": str(exc), "skipped": True})

    # ── 5. Burn captions ──────────────────────────────────────────────────────
    try:
        final_path, captioned = _ffmpeg.burn_captions(
            video_path=cropped_path,
            srt_path=srt_path or "__missing__.srt",
            heading_text=body.headingText,
        )
        record("burn_captions", {"finalPath": final_path, "captioned": captioned})
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=f"Caption burn failed: {exc}")

    log.info("Orchestrator complete → %s", final_path)

    return OrchestratorResponse(
        status="success",
        videoId=video_id,
        finalVideoPath=final_path,
        steps=steps,
    )
