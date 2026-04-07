"""
Router – POST /workflow/auto

Completely replaces the n8n logic natively in Python.
"""
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.schemas.workflow import WorkflowAutoRequest, WorkflowAutoResponse
from app.services.workflow import WorkflowService
from app.services.downloader import DownloadService
from app.services.ffmpeg import FFmpegService
from app.services.whisper import WhisperService
from app.services.youtube_upload import YouTubeUploadService
from app.utils.file_utils import extract_video_id
from app.utils.logger import get_logger

router = APIRouter(prefix="/workflow", tags=["6 - Auto Workflow"])
log    = get_logger("router.workflow")

_workflow = WorkflowService()
_downloader = DownloadService()
_ffmpeg = FFmpegService()
_whisper = WhisperService()

# In-memory dictionary to track job statuses
_jobs: Dict[str, Dict[str, Any]] = {}

@router.get(
    "/auth",
    summary="1. Authenticate YouTube Only",
    description="Run this once to link your Google account. Opens browser locally."
)
def authenticate_youtube():
    log.info("Checking YouTube Authentication...")
    try:
        YouTubeUploadService()
        return {"status": "success", "message": "YouTube is authenticated. You can safely run the auto workflow now."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/status/{job_id}",
    summary="3. Check Auto Workflow Status",
    description="Returns exactly what step the pipeline is currently executing."
)
def get_job_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job ID not found or already purged.")
    return _jobs[job_id]


def autonomous_task_runner(job_id: str, body: WorkflowAutoRequest) -> None:
    """Executes the pipeline completely in the background, updating the _jobs state dictionary continually."""
    def set_status(text: str, progress: int):
        log.info(f"JOB[{job_id}] - {text}")
        _jobs[job_id]["status"] = text
        _jobs[job_id]["progress"] = progress

    set_status("Initializing & Checking YouTube Auth...", 5)

    try:
        yt_svc = YouTubeUploadService()
    except Exception as e:
        set_status(f"FAILED (YouTube Auth Error): {e}", 0)
        return

    # 1. Fetch Trending if needed
    set_status("Fetching Trending Videos...", 15)
    if not body.videoUrl:
        try:
            videos = _workflow.fetch_trending_videos()
            if not videos:
                set_status("FAILED (No suitable trending videos found)", 0)
                return
            best_video = videos[0]
            target_url = best_video["videoUrl"]
            title = best_video["title"]
            channel = best_video["channelTitle"]
            views = best_video["viewCount"]
            tags = best_video["tags"]
        except Exception as e:
            set_status(f"FAILED (Trending Fetch Error): {e}", 0)
            return
    else:
        target_url = body.videoUrl
        title = "Provided Target URL"
        channel = "Unknown"
        views = "Unknown"
        tags = ""

    video_id = extract_video_id(target_url)

    # 2. Pipeline -> Download
    set_status(f"Downloading Video ({target_url})...", 30)
    try:
        dl = _downloader.download(target_url, quality=body.videoQuality)
    except Exception as e:
        set_status(f"FAILED (Download Error): {e}", 0)
        return

    # 3. Pipeline -> Crop
    set_status("Cropping & Generating 9:16 Short...", 45)
    try:
        cropped_path = _ffmpeg.crop_to_vertical(
            input_path=dl["filePath"],
            duration_sec=body.durationSec,
            start_sec=body.startSec,
        )
    except Exception as e:
        set_status(f"FAILED (Crop Error): {e}", 0)
        return

    # 4. Pipeline -> Transcribe
    set_status("Transcribing Audio via OpenAI Whisper...", 60)
    try:
        srt_path = _whisper.transcribe(video_path=cropped_path, model=body.whisperModel)
    except Exception as e:
        log.warning("Transcription skipped: %s", e)
        srt_path = "__missing__.srt"

    # 5. Metadata Generator (Groq/OpenRouter)
    set_status("Generating Viral Metadata via AI...", 75)
    metadata = _workflow.generate_metadata(title, channel, views, tags)
    heading = metadata.get("title", "")

    # 6. Pipeline -> Burn
    set_status("Burning Subtitles & Graphics...", 85)
    try:
        final_path, _ = _ffmpeg.burn_captions(
            video_path=cropped_path,
            srt_path=srt_path,
            heading_text=heading
        )
    except Exception as e:
        set_status(f"FAILED (Caption Burn Error): {e}", 0)
        return

    # 7. YouTube Uploading
    set_status("Uploading Final Video to YouTube natively...", 95)
    yt_url = final_path
    try:
        uploaded_id = yt_svc.upload_short(
            video_path=final_path,
            title=heading,
            description=metadata.get("full_description", heading),
            tags=[tag.replace('#', '') for tag in metadata.get("hashtags", "").split()]
        )
        yt_url = f"https://youtube.com/shorts/{uploaded_id}"
    except Exception as e:
        log.error("YouTube Upload Failed -> %s", e)
        # We don't abort, we still want to finish and send telegram

    # 8. Telegram Notification
    set_status("Executing final Telegram deliveries...", 99)
    try:
        _workflow.send_telegram_alert(
            short_title=heading,
            short_url=yt_url,
            orig_title=title,
            orig_views=views
        )
        _workflow.send_telegram_video(
            video_path=final_path,
            caption=f"🎥 *{heading}*\n\n_{metadata.get('description', '')}_"
        )
    except Exception as e:
        log.error(f"Telegram failed: {e}")

    # Done!
    set_status("COMPLETE", 100)
    _jobs[job_id]["results"] = {
        "videoId": video_id,
        "youtubeUrl": yt_url,
        "finalLocalPath": final_path,
        "metadata": metadata
    }


@router.post(
    "/auto",
    summary="2. Start Background Auto Workflow",
    description=(
        "Kicks off the autonomous workflow completely in the background instantly! "
        "Returns a jobId that you can use to track the progress."
    ),
)
def run_autonomous_workflow(body: WorkflowAutoRequest, bg_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "Queued",
        "progress": 0,
        "results": None
    }
    
    # Delegate the ultra long 5-minute task into the FastAPI background pool!
    bg_tasks.add_task(autonomous_task_runner, job_id, body)
    
    return {
        "status": "success",
        "message": "Workflow triggered in the background successfully!",
        "job_id": job_id,
        "tracker_url": f"/workflow/status/{job_id}"
    }
