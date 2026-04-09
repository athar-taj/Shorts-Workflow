"""
services/style_service.py - Maps category → visual/cinematic style prompt suffix.
"""

from __future__ import annotations
from pathlib import Path

from app.ai_shorts.schemas import Category
from app.utils.logger import get_logger
from app.config import settings as config

logger = get_logger(__name__)

# Category → Stable Diffusion style descriptor
_STYLE_MAP: dict[Category, str] = {
    Category.KIDS_FUN_STORY: (
        "cute cartoon, colorful, 3D animated style, cheerful, "
        "soft lighting, child-friendly, vibrant palette"
    ),
    Category.HORROR_SHORT: (
        "dark cinematic lighting, realistic, moody, ominous atmosphere, "
        "desaturated colors, dramatic shadows, horror film grain"
    ),
    Category.MOTIVATIONAL_STORY: (
        "inspirational, golden hour lighting, cinematic realism, "
        "uplifting colors, warm tones, soft bokeh background"
    ),
    Category.COMEDY_SKETCH: (
        "simple cartoon, exaggerated expressions, bright pop-art colors, "
        "comic book style, fun and energetic"
    ),
}


class StyleService:
    """Provides visual style descriptors per category."""

    def get_style(self, category: Category) -> str:
        """
        Return a style string to append to image prompts.

        Args:
            category: The selected category.

        Returns:
            Style descriptor string.
        """
        style = _STYLE_MAP.get(category, "high quality, detailed illustration")
        logger.debug("Style for '%s': %s", category.value, style)
        return style



