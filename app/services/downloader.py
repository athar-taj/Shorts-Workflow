"""
Service – YouTube video download via yt-dlp.

Responsibility:
  Download a YouTube video to the configured TMP directory.
  Returns the absolute path of the saved file.
"""

import glob
import os

import yt_dlp

from app.config import settings
from app.utils.ffmpeg_resolver import get_ffmpeg_binary
from app.utils.file_utils import extract_video_id, build_tmp_path, file_size_mb
from app.utils.logger import get_logger

log = get_logger("service.downloader")


class DownloadService:
    """Encapsulates all yt-dlp download logic."""

    def download(self, video_url: str, quality: str = "best") -> dict:
        """
        Download a YouTube video and return metadata.

        Args:
            video_url: Full YouTube URL.
            quality: Requested video quality ('2160p', '1080p', '720p', 'best').

        Returns:
            dict with keys: videoId, filePath, cached (bool), fileSizeMb.

        Raises:
            ValueError: If the URL is invalid.
            RuntimeError: If the download fails or the output file is missing.
        """
        video_id = extract_video_id(video_url)
        out_path = build_tmp_path(video_id, ".mp4")

        # Cache hit – skip re-downloading
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            log.info("Cache hit — skipping download: %s", out_path)
            return {
                "videoId": video_id,
                "filePath": out_path,
                "cached": True,
                "fileSizeMb": file_size_mb(out_path),
            }

        # Resolve ffmpeg path for yt-dlp (needed if merging streams)
        try:
            ffmpeg_loc = get_ffmpeg_binary()  # Pass full executable path, not just dirname
        except RuntimeError:
            ffmpeg_loc = None   # yt-dlp will try PATH itself

        # Build yt-dlp format string based on quality
        # Fallback to pure mp4 download if system FFmpeg/ffprobe is unavailable (since our bundled fallback lacks ffprobe)
        import shutil
        has_full_ffmpeg_suite = shutil.which("ffmpeg") and shutil.which("ffprobe")
        
        if has_full_ffmpeg_suite:
            qual_format = {
                "2160p": "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            }.get(quality, "best[ext=mp4]/best")
        else:
            log.warning("System FFprobe is missing. Falling back to pre-merged pure formats without merging.")
            qual_format = "best[ext=mp4]/best"

        ydl_opts = {
            "format": qual_format,
            "outtmpl": os.path.join(settings.tmp_dir, f"{video_id}.%(ext)s"),
            "merge_output_format": "mp4",
            "ffmpeg_location": ffmpeg_loc,
            "quiet": True,
            "no_warnings": True,
            "source_address": "0.0.0.0",   # Force IPv4 (fixes WinError 10061 "Target machine actively refused it")
            "retries": 10,                 # Retry on HTTP errors
            "fragment_retries": 10,        # Retry on fragmented connection drops
            "nocheckcertificate": True,    # Bypass strict SSL certificate checks  
        }

        log.info("Downloading %s → %s", video_url, out_path)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except yt_dlp.utils.DownloadError as exc:
            raise RuntimeError(f"yt-dlp download failed: {exc}") from exc

        # yt-dlp may choose a different extension; rename to .mp4 if needed
        if not os.path.exists(out_path):
            candidates = glob.glob(os.path.join(settings.tmp_dir, f"{video_id}.*"))
            candidates = [c for c in candidates if not c.endswith(".part")]
            if candidates:
                os.rename(candidates[0], out_path)
            else:
                raise RuntimeError(
                    "Downloaded file not found after yt-dlp run. "
                    f"Searched: {settings.tmp_dir}/{video_id}.*"
                )

        size = file_size_mb(out_path)
        log.info("Download complete: %s (%.2f MB)", out_path, size)

        return {
            "videoId": video_id,
            "filePath": out_path,
            "cached": False,
            "fileSizeMb": size,
        }
