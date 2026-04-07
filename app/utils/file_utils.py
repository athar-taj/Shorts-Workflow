"""
Shared file-system utilities used across services.

All path helpers resolve the storage directory from `settings.tmp_dir`
at call-time, so any .env override is respected without restarting.
"""

import glob
import os
import re


# ── Internal helper ───────────────────────────────────────────────────────────

def _storage_dir() -> str:
    """Return the configured video storage directory (lazy, avoids circular imports)."""
    from app.config import settings   # noqa: PLC0415
    return settings.tmp_dir


# ── Public API ────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str:
    """
    Parse a YouTube video ID from any supported URL format.

    Supports:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID

    Raises:
        ValueError: If no valid video ID can be extracted.
    """
    pattern = r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"Cannot extract a valid YouTube video ID from URL: {url!r}")
    return match.group(1)


def sanitize_filename(name: str) -> str:
    """Strip characters that are invalid in Windows/Linux filenames."""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def build_tmp_path(video_id: str, suffix: str = ".mp4") -> str:
    """Return an absolute path inside the storage directory for a given video ID and suffix."""
    return os.path.join(_storage_dir(), f"{video_id}{suffix}")


def find_tmp_files(video_id: str) -> list[str]:
    """Return all files in the storage directory whose name starts with video_id."""
    pattern = os.path.join(_storage_dir(), f"{video_id}*")
    return glob.glob(pattern)


def file_size_mb(path: str) -> float:
    """Return file size in megabytes, rounded to 2 decimal places."""
    return round(os.path.getsize(path) / (1024 * 1024), 2)
