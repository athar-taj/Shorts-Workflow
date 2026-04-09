"""
services/category_service.py - Rotates through video categories without repetition.
"""

from __future__ import annotations
from pathlib import Path

import json

from app.config import settings as config
from app.ai_shorts.schemas import Category
from app.utils.logger import get_logger

logger = get_logger(__name__)

_STATE_FILE: Path = config.MEMORY_DIR / "_category_state.json"


class CategoryService:
    """
    Cycles through all categories in a round-robin fashion.
    State is persisted to disk so it survives restarts.
    """

    def __init__(self) -> None:
        self._state: dict = self._load_state()
        logger.info("CategoryService initialised. Current index: %d", self._state["index"])

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_state(self) -> dict:
        if _STATE_FILE.exists():
            try:
                return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"index": 0}

    def _save_state(self) -> None:
        _STATE_FILE.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    # ── Public API ─────────────────────────────────────────────────────────────

    def next_category(self) -> Category:
        """Return the next category in rotation and advance the counter."""
        categories = list(Category)
        idx = self._state["index"] % len(categories)
        selected = categories[idx]
        self._state["index"] = (idx + 1) % len(categories)
        self._save_state()
        logger.info("Selected category: %s", selected.value)
        return selected

    def current_category(self) -> Category:
        """Return the current category without advancing."""
        categories = list(Category)
        idx = self._state["index"] % len(categories)
        return categories[idx]



