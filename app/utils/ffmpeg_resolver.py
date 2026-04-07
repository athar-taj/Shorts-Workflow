"""
FFmpeg binary resolver.

Priority:
  1. System FFmpeg on PATH  (fastest, user-installed)
  2. imageio-ffmpeg bundled binary  (fallback, installed via pip)

Import `get_ffmpeg_binary()` anywhere FFmpeg is needed.
"""

import os
import shutil
from app.utils.logger import get_logger

log = get_logger("utils.ffmpeg_resolver")

_cached_path: str | None = None


def get_ffmpeg_binary() -> str:
    """
    Return the ffmpeg executable path.

    Raises:
        RuntimeError: If neither system ffmpeg nor imageio-ffmpeg is available.
    """
    global _cached_path
    if _cached_path:
        return _cached_path

    # 1. System PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        log.info("Using system FFmpeg: %s", system_ffmpeg)
        _cached_path = system_ffmpeg
        return _cached_path

    # 2. imageio-ffmpeg bundled binary
    try:
        from imageio_ffmpeg import get_ffmpeg_exe  # type: ignore
        bundled = get_ffmpeg_exe()
        
        # Whisper requires the executable to be named EXACTLY "ffmpeg" or "ffmpeg.exe"
        # Since imageio-ffmpeg uses files like "ffmpeg-win-x86_64-v7.1.exe", we copy it.
        if "ffmpeg.exe" not in bundled.lower() and not bundled.endswith("ffmpeg"):
            project_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".bin")
            os.makedirs(project_bin, exist_ok=True)
            local_ffmpeg = os.path.join(project_bin, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            
            if not os.path.exists(local_ffmpeg):
                log.info("Copying bundled FFmpeg to %s so Whisper can find it...", local_ffmpeg)
                shutil.copy2(bundled, local_ffmpeg)
                if os.name != "nt":
                    os.chmod(local_ffmpeg, 0o755)
            
            log.info("Using local bundled FFmpeg: %s", local_ffmpeg)
            _cached_path = local_ffmpeg
            return _cached_path

        log.info("Using imageio-ffmpeg bundled binary: %s", bundled)
        _cached_path = bundled
        return _cached_path
    except ImportError:
        pass

    raise RuntimeError(
        "FFmpeg not found. Either install FFmpeg system-wide "
        "(https://ffmpeg.org/download.html) or run: py -m pip install imageio[ffmpeg]"
    )
