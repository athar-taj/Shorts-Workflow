"""
services/video_service.py - Assembles final 9:16 vertical video using FFmpeg.

Features:
- Ken Burns (zoom) effect per image
- Vertical format (1080×1920)
- Merges image slideshow with merged audio
- Outputs MP4
"""

from __future__ import annotations
from pathlib import Path

import subprocess
import uuid

from app.config import settings as config
from app.ai_shorts.schemas import StoryOutput
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SCENE_DURATION_S: float = config.SCENE_DURATION_S
_ZOOM_SPEED: float = config.ZOOM_SPEED


class VideoService:
    """
    Builds the final video from scene images + merged audio using FFmpeg.
    Each image is animated with a subtle Ken Burns zoom/pan effect.
    """

    def create_video(self, story: StoryOutput, audio_path: str) -> str:
        """
        Assembles the video.

        Args:
            story:      StoryOutput with image_path populated in each scene.
            audio_path: Path to the merged audio WAV file.

        Returns:
            Absolute path to the output MP4 file.
        """
        output_path = config.VIDEO_DIR / f"short_{uuid.uuid4().hex[:8]}.mp4"

        image_paths = [scene.image_path for scene in story.scenes if scene.image_path]
        if not image_paths:
            raise ValueError("No images available to assemble video.")

        logger.info("Assembling video from %d images…", len(image_paths))

        # Step 1 – Build animated image clips (one per scene)
        clip_paths = [
            self._make_zoom_clip(img_path, idx)
            for idx, img_path in enumerate(image_paths, start=1)
        ]

        # Step 2 – Concatenate all clips
        concat_path = self._concatenate_clips(clip_paths)

        # Step 3 – Mix with audio
        self._mux_audio(concat_path, audio_path, str(output_path))

        logger.info("Video created: %s", output_path)
        return str(output_path)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _make_zoom_clip(self, image_path: str, idx: int) -> str:
        """Apply Ken Burns zoom effect to a single image → temporary MP4 clip."""
        clip_path = config.VIDEO_DIR / f"clip_{uuid.uuid4().hex[:6]}_{idx}.mp4"
        total_frames = int(_SCENE_DURATION_S * config.VIDEO_FPS)
        w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT

        # zoompan filter: slow zoom from 1x to 1.15x with centre pan
        zoompan_filter = (
            f"scale={w * 2}:{h * 2},"
            f"zoompan=z='min(zoom+{_ZOOM_SPEED},1.15)':"
            f"d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={w}x{h},fps={config.VIDEO_FPS}"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", zoompan_filter,
            "-t", str(_SCENE_DURATION_S),
            "-c:v", config.VIDEO_CODEC,
            "-pix_fmt", "yuv420p",
            "-an",
            str(clip_path),
        ]

        self._run_ffmpeg(cmd, label=f"zoom clip {idx}")
        return str(clip_path)

    @staticmethod
    def _concatenate_clips(clip_paths: list[str]) -> str:
        """Write a concat list and merge all clips into one silent video."""
        concat_list = config.VIDEO_DIR / f"concat_{uuid.uuid4().hex[:6]}.txt"
        concat_list.write_text(
            "\n".join(f"file '{p}'" for p in clip_paths), encoding="utf-8"
        )

        out_path = config.VIDEO_DIR / f"concat_out_{uuid.uuid4().hex[:6]}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(out_path),
        ]
        VideoService._run_ffmpeg(cmd, label="concatenation")
        return str(out_path)

    @staticmethod
    def _mux_audio(video_path: str, audio_path: str, output_path: str) -> None:
        """Combine the video track with the audio track."""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", config.AUDIO_CODEC,
            "-shortest",
            output_path,
        ]
        VideoService._run_ffmpeg(cmd, label="audio mux")

    @staticmethod
    def _run_ffmpeg(cmd: list[str], label: str = "ffmpeg") -> None:
        """Run an FFmpeg command, raising a RuntimeError on failure."""
        logger.debug("FFmpeg [%s]: %s", label, " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("FFmpeg [%s] stderr: %s", label, result.stderr[-500:])
            raise RuntimeError(
                f"FFmpeg failed during '{label}':\n{result.stderr[-300:]}"
            )
        logger.info("FFmpeg [%s] completed successfully.", label)



