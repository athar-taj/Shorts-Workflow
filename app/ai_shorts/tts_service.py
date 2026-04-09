"""
services/tts_service.py - Generates narration audio using Coqui TTS
"""

from __future__ import annotations
from pathlib import Path

import uuid
from typing import Any

from app.config import settings as config
from app.ai_shorts.schemas import StoryOutput
from app.utils.logger import get_logger

logger = get_logger(__name__)

_tts_engine: Any | None = None

def _get_tts() -> Any:
    global _tts_engine
    if _tts_engine is not None: return _tts_engine

    try:
        from TTS.api import TTS
        logger.info("Loading Coqui TTS model: %s", config.TTS_MODEL)
        _tts_engine = TTS(model_name=config.TTS_MODEL, progress_bar=False, gpu=False)
        return _tts_engine
    except Exception as exc:
        logger.error("Failed to load TTS: %s", exc)
        raise RuntimeError(f"TTS engine failed: {exc}")

class TTSService:
    def generate_for_story(self, story: StoryOutput) -> str:
        if config.DRY_RUN:
            paths = [self._create_silence(i, duration_s=config.SCENE_DURATION_S) for i in range(1, len(story.scenes) + 1)]
            for s, p in zip(story.scenes, paths): s.audio_path = p
            return self._merge_audio(paths)

        tts = _get_tts()
        paths = []
        for i, scene in enumerate(story.scenes, start=1):
            out_path = config.AUDIO_DIR / f"{uuid.uuid4().hex[:8]}_scene{i}.wav"
            try:
                # Note: some older TTS models don't take 'speed'. If it fails, fallback to simple generation.
                try:
                    tts.tts_to_file(text=scene.text, file_path=str(out_path), speed=config.TTS_SPEAKER_SPEED)
                except TypeError:
                    tts.tts_to_file(text=scene.text, file_path=str(out_path))
                scene.audio_path = str(out_path)
                paths.append(str(out_path))
            except Exception as exc:
                logger.error("TTS failed for scene %d: %s", i, exc)
                silence = self._create_silence(i, duration_s=config.SCENE_DURATION_S)
                scene.audio_path = silence
                paths.append(silence)

        return self._merge_audio(paths)

    @staticmethod
    def _create_silence(scene_num: int, duration_s: float = 3.0) -> str:
        import wave, struct
        path = config.AUDIO_DIR / f"silence_scene{scene_num}.wav"
        n_frames = int(config.TTS_SAMPLE_RATE * duration_s)
        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(config.TTS_SAMPLE_RATE)
            wf.writeframes(b"\x00\x00" * n_frames)
        return str(path)

    @staticmethod
    def _merge_audio(paths: list[str]) -> str:
        import wave
        merged_path = config.AUDIO_DIR / f"merged_{uuid.uuid4().hex[:8]}.wav"
        with wave.open(str(merged_path), "w") as outf:
            params_set = False
            for p in paths:
                if not Path(p).exists(): continue
                with wave.open(p, "r") as inf:
                    if not params_set:
                        outf.setparams(inf.getparams())
                        params_set = True
                    outf.writeframes(inf.readframes(inf.getnframes()))
        return str(merged_path)



