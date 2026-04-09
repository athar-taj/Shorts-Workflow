"""
services/image_service.py - Generates images using Stable Diffusion (CPU-only).
"""

from __future__ import annotations
from pathlib import Path

import uuid
from typing import Any

from app.config import settings as config
from app.ai_shorts.schemas import Scene, StoryOutput
from app.utils.logger import get_logger

logger = get_logger(__name__)

_sd_pipe: Any | None = None
_loaded_model: str | None = None

def _load_sd_pipeline(model_id: str) -> Any:
    import torch
    from diffusers import AutoPipelineForText2Image, StableDiffusionPipeline

    logger.info("Loading image model: %s (CPU)", model_id)
    if "sdxl-turbo" in model_id.lower() or "turbo" in model_id.lower():
        pipe = AutoPipelineForText2Image.from_pretrained(
            model_id, torch_dtype=torch.float32, token=config.HF_TOKEN or None
        )
    else:
        pipe = StableDiffusionPipeline.from_pretrained(
            model_id, torch_dtype=torch.float32, token=config.HF_TOKEN or None
        )

    pipe = pipe.to("cpu")
    logger.info("Image model ready: %s", model_id)
    return pipe

def _get_sd_pipeline() -> Any:
    global _sd_pipe, _loaded_model
    if _sd_pipe is not None:
        return _sd_pipe

    for model_id in (config.IMAGE_MODEL_PRIMARY, config.IMAGE_MODEL_FALLBACK):
        try:
            _sd_pipe = _load_sd_pipeline(model_id)
            _loaded_model = model_id
            return _sd_pipe
        except Exception as exc:
            logger.warning("Could not load image model '%s': %s", model_id, exc)

    raise RuntimeError("No image generation model could be loaded.")

class ImageService:
    def generate_for_story(self, story: StoryOutput, style: str) -> StoryOutput:
        if config.DRY_RUN:
            for i, scene in enumerate(story.scenes, start=1):
                scene.image_path = self._create_placeholder(i, config.IMAGE_RESOLUTION[0], config.IMAGE_RESOLUTION[1], text=f"Scene {i}: {scene.image_prompt[:30]}...")
            return story

        pipe = _get_sd_pipeline()
        width, height = config.IMAGE_RESOLUTION

        for i, scene in enumerate(story.scenes, start=1):
            full_prompt = f"{scene.image_prompt}, {style}"
            logger.info("Generating image %d/%d: %s…", i, len(story.scenes), full_prompt[:60])
            try:
                result = pipe(
                    full_prompt,
                    num_inference_steps=config.IMAGE_INFERENCE_STEPS,
                    width=width,
                    height=height,
                    guidance_scale=config.IMAGE_GUIDANCE_SCALE if "turbo" not in (_loaded_model or "").lower() else 0.0,
                )
                image = result.images[0]
                img_path = config.IMAGE_DIR / f"{uuid.uuid4().hex[:8]}_scene{i}.png"
                image.save(str(img_path), format=config.IMAGE_FORMAT)
                scene.image_path = str(img_path)
            except Exception as exc:
                logger.error("Image generation failed for scene %d: %s", i, exc)
                scene.image_path = self._create_placeholder(i, width, height)

        return story

    @staticmethod
    def _create_placeholder(scene_num: int, width: int, height: int, text: str = "") -> str:
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (width, height), color=(30, 60, 90))
            draw = ImageDraw.Draw(img)
            draw.text((10, height // 2), text or f"Scene {scene_num}", fill=(200, 200, 200))
            path = config.IMAGE_DIR / f"placeholder_scene{scene_num}.png"
            img.save(str(path))
            return str(path)
        except Exception as exc:
            logger.error("Placeholder failed: %s", exc)
            return ""



