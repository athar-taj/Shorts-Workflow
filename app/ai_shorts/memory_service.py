"""
services/memory_service.py - Manages episodic story memory (series system).
Each series is stored as a JSON file under MEMORY_DIR.
"""

from __future__ import annotations
from pathlib import Path

import json
import uuid

from app.config import settings as config
from app.ai_shorts.schemas import Category, EpisodeMemory
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryService:
    """
    Persistent episode/series memory.

    * ``create_series``    → starts a fresh series and returns its EpisodeMemory.
    * ``get_series``       → reads an existing series by ID.
    * ``advance_chapter``  → increments chapter counter and updates summary.
    * ``list_series``      → lists all active series.
    """

    def __init__(self) -> None:
        self._dir: Path = config.MEMORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        logger.info("MemoryService initialised. Memory dir: %s", self._dir)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _path(self, series_id: str) -> Path:
        return self._dir / f"{series_id}.json"

    def _write(self, memory: EpisodeMemory) -> None:
        self._path(memory.series_id).write_text(
            memory.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.debug("Memory saved: %s (chapter %d)", memory.series_id, memory.chapter)

    def _read(self, series_id: str) -> EpisodeMemory:
        path = self._path(series_id)
        if not path.exists():
            raise FileNotFoundError(f"Series '{series_id}' not found in memory.")
        data = json.loads(path.read_text(encoding="utf-8"))
        return EpisodeMemory(**data)

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_series(self, category: Category, title: str | None = None) -> EpisodeMemory:
        """Create and persist a brand-new episode series."""
        series_id = str(uuid.uuid4())[:8]
        memory = EpisodeMemory(
            series_id=series_id,
            category=category,
            chapter=1,
            summary="",
            title=title,
        )
        self._write(memory)
        logger.info("Created new series '%s' for category '%s'", series_id, category.value)
        return memory

    def get_series(self, series_id: str) -> EpisodeMemory:
        """Load an existing series from disk."""
        memory = self._read(series_id)
        logger.info(
            "Loaded series '%s' — chapter %d / category %s",
            series_id,
            memory.chapter,
            memory.category.value,
        )
        return memory

    def advance_chapter(self, series_id: str, new_summary: str, title: str | None = None) -> EpisodeMemory:
        """
        Increment chapter number, optionally update title and summary.

        Args:
            series_id:   ID of the series to update.
            new_summary: Short summary of the latest episode (for context in next gen).
            title:       Optional new title override.

        Returns:
            Updated EpisodeMemory.
        """
        memory = self._read(series_id)
        memory.chapter += 1
        memory.summary = new_summary
        if title:
            memory.title = title
        self._write(memory)
        logger.info("Advanced series '%s' to chapter %d", series_id, memory.chapter)
        return memory

    def list_series(self) -> list[EpisodeMemory]:
        """Return all persisted series sorted by series_id."""
        memories: list[EpisodeMemory] = []
        for p in sorted(self._dir.glob("*.json")):
            if p.stem.startswith("_"):
                continue   # skip internal state files
            try:
                memories.append(EpisodeMemory(**json.loads(p.read_text(encoding="utf-8"))))
            except Exception as exc:
                logger.warning("Could not parse memory file %s: %s", p.name, exc)
        return memories



