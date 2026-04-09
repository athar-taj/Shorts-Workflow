"""
services/workflow_service.py - Main pipeline orchestrator.

Executes all 8 pipeline steps in sequence:
1. Select category
2. Get or create story memory
3. Generate story (LLM)
4. Process/clean scenes
5. Generate images (Diffusion)
6. Generate audio (TTS)
7. Create video (FFmpeg)
8. Update memory + return result
"""

from __future__ import annotations
from pathlib import Path

from app.config import settings as config
from app.ai_shorts.schemas import Category, EpisodeMemory, PipelineResult
from app.ai_shorts.category_service import CategoryService
from app.ai_shorts.image_service import ImageService
from app.ai_shorts.memory_service import MemoryService
from app.ai_shorts.scene_service import SceneService
from app.ai_shorts.story_service import StoryService
from app.ai_shorts.style_service import StyleService
from app.ai_shorts.tts_service import TTSService
from app.ai_shorts.video_service import VideoService
from app.services.youtube_upload import YouTubeUploadService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowService:
    """
    Orchestrates the full AI Shorts generation pipeline.

    All sub-services are instantiated once; models are lazily loaded on
    first use (singleton pattern inside each service).
    """

    def __init__(self) -> None:
        self.category_svc = CategoryService()
        self.memory_svc = MemoryService()
        self.story_svc = StoryService()
        self.scene_svc = SceneService()
        self.style_svc = StyleService()
        self.image_svc = ImageService()
        self.tts_svc = TTSService()
        self.video_svc = VideoService()
        self.yt_svc = None  # Lazy load to avoid triggering OAuth unexpectedly
        logger.info("WorkflowService ready — all sub-services initialised.")

    def run(
        self,
        series_id: str | None = None,
        category_override: Category | None = None,
        upload_to_youtube: bool = False,
    ) -> PipelineResult:
        """
        Execute the full pipeline and return the result.

        Args:
            series_id:         If provided, continue an existing series.
            category_override: Force a specific category (ignores rotation).
            upload_to_youtube: If True, uploads the final video to YouTube via OAuth.

        Returns:
            PipelineResult with video_path, title, category, chapter, and optionally youtube_url.
        """
        # ── Step 1: Select category ────────────────────────────────────────────
        if category_override:
            category = category_override
            logger.info("[1/8] Category override: %s", category.value)
        else:
            category = self.category_svc.next_category()
            logger.info("[1/8] Category selected: %s", category.value)

        # ── Step 2: Get or create memory ───────────────────────────────────────
        memory: EpisodeMemory | None
        if series_id:
            try:
                memory = self.memory_svc.get_series(series_id)
                logger.info("[2/8] Continuing series '%s' chapter %d", series_id, memory.chapter)
            except FileNotFoundError:
                logger.warning("[2/8] Series '%s' not found — starting fresh.", series_id)
                memory = self.memory_svc.create_series(category)
        else:
            memory = self.memory_svc.create_series(category)
            logger.info("[2/8] New series created: '%s'", memory.series_id)

        # ── Step 3: Generate story ─────────────────────────────────────────────
        logger.info("[3/8] Generating story…")
        story = self.story_svc.generate(category=memory.category, memory=memory)

        # ── Step 4: Process scenes ─────────────────────────────────────────────
        logger.info("[4/8] Processing scenes…")
        story = self.scene_svc.process(story)

        # ── Step 5: Generate images ────────────────────────────────────────────
        logger.info("[5/8] Generating images…")
        visual_style = self.style_svc.get_style(memory.category)
        story = self.image_svc.generate_for_story(story, visual_style)

        # ── Step 6: Generate audio ─────────────────────────────────────────────
        logger.info("[6/8] Generating audio…")
        audio_path = self.tts_svc.generate_for_story(story)

        # ── Step 7: Create video ───────────────────────────────────────────────
        logger.info("[7/8] Assembling video…")
        video_path = self.video_svc.create_video(story, audio_path)

        # ── Step 8: Update memory & return ────────────────────────────────────
        logger.info("[8/8] Updating series memory…")
        summary = " ".join(s.text for s in story.scenes)[:300]
        if memory.chapter == 1 and not series_id:
            # first episode — memory record already exists; just update title
            self.memory_svc.advance_chapter(
                memory.series_id, new_summary=summary, title=story.title
            )
        else:
            self.memory_svc.advance_chapter(
                memory.series_id, new_summary=summary, title=story.title
            )

        result = PipelineResult(
            video_path=video_path,
            title=story.title,
            category=memory.category.value,
            chapter=memory.chapter,
        )

        # ── Step 9: YouTube Upload ─────────────────────────────────────────────
        if upload_to_youtube:
            logger.info("[9/9] Uploading to YouTube…")
            if not self.yt_svc:
                self.yt_svc = YouTubeUploadService()
            
            try:
                # Add default shorts category and basic tags
                yt_id = self.yt_svc.upload_short(
                    video_path=video_path,
                    title=story.title,
                    description=summary + "\n\n#shorts #aishorts #" + memory.category.value,
                    category_id="24", # Entertainment
                )
                result.youtube_url = f"https://youtube.com/shorts/{yt_id}"
                logger.info("YouTube upload successful: %s", result.youtube_url)
            except Exception as e:
                logger.error("YouTube upload failed: %s", e)

        logger.info(
            "Pipeline complete ✓ | title='%s' | video=%s",
            result.title,
            result.video_path,
        )
        return result



