"""
Service – Audio transcription via OpenAI Whisper CLI.

Responsibility:
  Extract audio from a video and produce an SRT subtitle file
  using the `whisper` command-line tool (openai-whisper package).

Prerequisites:
  pip install openai-whisper
  FFmpeg must be on PATH (Whisper also needs it internally).
"""

import os
import subprocess
import sys

from app.config import settings
from app.utils.ffmpeg_resolver import get_ffmpeg_binary
from app.utils.logger import get_logger

log = get_logger("service.whisper")


class WhisperService:
    """Wraps the Whisper CLI to produce SRT files from video paths."""

    def transcribe(self, video_path: str, model: str | None = None, task: str = "transcribe") -> str:
        """
        Transcribe a video file and write a matching .srt next to it.

        Args:
            video_path: Absolute path to the video file.
            model:      Whisper model name. Falls back to settings.default_whisper_model.
            task:       'transcribe' (original language) or 'translate' (to English).
                        Use 'translate' for Hindi voice → English captions.

        Returns:
            Absolute path of the generated SRT file.
        """

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        model      = model or settings.default_whisper_model
        base, _    = os.path.splitext(video_path)
        out_dir    = os.path.dirname(video_path) or settings.tmp_dir
        wav_path   = f"{base}_audio.wav"
        srt_path   = f"{base}.srt"

        # ── Step 1: Extract audio ────────────────────────────────────────
        self._extract_audio(video_path, wav_path)

        # ── Step 2: Run Whisper ─────────────────────────────────────────
        self._run_whisper(wav_path, model, out_dir, task=task)

        # ── Step 3: Locate / rename Whisper output ──────────────────────
        import glob

        pattern = os.path.join(out_dir, f"{os.path.basename(base)}*.srt")
        matches = glob.glob(pattern)

        if matches:
            matches = [m for m in matches if os.path.abspath(m) != os.path.abspath(srt_path)]
            if matches:
                whisper_output = matches[0]
                if os.path.exists(srt_path):
                    os.remove(srt_path)
                os.rename(whisper_output, srt_path)

        # ── Step 4: Cleanup temp WAV ─────────────────────────────────────
        if os.path.exists(wav_path):
            os.remove(wav_path)
            log.debug("Removed temp WAV: %s", wav_path)

        if not os.path.exists(srt_path):
            raise RuntimeError(
                f"Whisper completed but SRT file was not found at: {srt_path}"
            )

        log.info("Transcription complete (task=%s): %s", task, srt_path)
        return srt_path

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_audio(self, video_path: str, wav_path: str) -> None:
        """Use FFmpeg to extract 16 kHz mono audio from the video."""
        cmd = [
            get_ffmpeg_binary(), "-y",
            "-i", video_path,
            "-vn",
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            wav_path,
        ]
        log.info("Extracting audio: %s → %s", video_path, wav_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr[-800:]}")

    def _run_whisper(self, wav_path: str, model: str, out_dir: str, task: str = "transcribe") -> None:
        """Invoke the `whisper` CLI using the python executable."""
        cmd = [
            sys.executable, "-m", "whisper", wav_path,
            "--model", model,
            "--output_format", "srt",
            "--output_dir", out_dir,
            "--task", task,   # 'transcribe' or 'translate' (always outputs English when translate)
        ]
        # For translate task, let Whisper auto-detect the source language (Hindi)
        if task == "transcribe":
            cmd.extend(["--language", settings.whisper_language])

        log.info("Running Whisper (model=%s, task=%s): %s", model, task, wav_path)
        ffmpeg_dir = os.path.dirname(get_ffmpeg_binary())
        env = os.environ.copy()
        env["PATH"] = f"{ffmpeg_dir}{os.pathsep}{env.get('PATH', '')}"

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            log.error("Whisper stderr:\n%s", result.stderr)
            raise RuntimeError(f"Whisper transcription failed: {result.stderr[-800:]}")
