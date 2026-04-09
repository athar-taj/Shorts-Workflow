"""
services/scene_service.py - Validates and cleans scenes returned by the story LLM.
"""

from __future__ import annotations
from pathlib import Path

import re

from app.config import settings as config
from app.ai_shorts.schemas import Scene, StoryOutput, VoiceType
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_SCENE_WORDS = 24   # soft cap per scene narration


def _word_count(text: str) -> int:
    return len(text.split())


def _trim_to_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    trimmed = " ".join(words[:max_words])
    logger.warning("Scene text trimmed from %d to %d words.", len(words), max_words)
    return trimmed + "…"


def _sanitise_prompt(prompt: str) -> str:
    """Remove any accidentally-injected special tokens or markup."""
    prompt = re.sub(r"<[^>]+>", "", prompt)   # strip HTML/XML-like tags
    return prompt.strip()


class SceneService:
    """
    Validates, cleans, and ensures completeness of story scenes.

    Rules enforced:
    * At most MAX_SCENES scenes per story.
    * Each scene text ≤ _MAX_SCENE_WORDS words.
    * image_prompt must be non-empty.
    * voice must be a valid VoiceType.
    """

    def process(self, story: StoryOutput) -> StoryOutput:
        """
        Apply all cleaning/validation rules to the story's scenes.

        Args:
            story: Raw StoryOutput from the story service.

        Returns:
            Cleaned StoryOutput (mutated in-place and returned).
        """
        logger.info("Processing %d scenes for story '%s'", len(story.scenes), story.title)

        # Enforce max scene count
        if len(story.scenes) > config.MAX_SCENES:
            logger.warning(
                "Truncating scenes from %d to %d", len(story.scenes), config.MAX_SCENES
            )
            story.scenes = story.scenes[: config.MAX_SCENES]

        cleaned: list[Scene] = []
        for i, scene in enumerate(story.scenes, start=1):
            # Trim narration text
            scene.text = _trim_to_words(scene.text.strip(), _MAX_SCENE_WORDS)

            # Sanitise image prompt
            scene.image_prompt = _sanitise_prompt(scene.image_prompt)
            if not scene.image_prompt:
                scene.image_prompt = f"Cinematic scene {i} related to: {story.title}"
                logger.warning("Scene %d had empty image_prompt; using fallback.", i)

            # Validate voice type
            try:
                scene.voice = VoiceType(scene.voice)
            except ValueError:
                scene.voice = VoiceType.NARRATOR

            logger.debug(
                "Scene %d: voice=%s | words=%d | prompt_len=%d",
                i,
                scene.voice,
                _word_count(scene.text),
                len(scene.image_prompt),
            )
            cleaned.append(scene)

        story.scenes = cleaned
        logger.info("Scene processing complete. %d scenes ready.", len(cleaned))
        return story



