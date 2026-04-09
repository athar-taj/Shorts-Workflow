"""
services/story_service.py - Generates story JSON using a HuggingFace LLM (CPU-only).
"""

from __future__ import annotations
from pathlib import Path

import json
import re
import textwrap
from typing import Any

from app.config import settings as config
from app.ai_shorts.schemas import Category, EpisodeMemory, Scene, StoryOutput, VoiceType
from app.utils.logger import get_logger

logger = get_logger(__name__)

_pipeline: Any | None = None
_loaded_model_name: str | None = None

_DRY_RUN_STORIES: dict[str, dict] = {
    "kids_fun_story": {
        "title": "The Magic Rainbow Bunny",
        "scenes": [
            {"text": "Once upon a time, a tiny bunny found a rainbow hidden inside a cloud!", "image_prompt": "cute cartoon bunny jumping into a rainbow cloud", "voice": "narrator"},
            {"text": "The bunny slid down the rainbow and landed in a field of giant lollipops.", "image_prompt": "cartoon bunny sliding down rainbow into candy field", "voice": "narrator"},
            {"text": "'Wow!' cried the bunny. 'This is the sweetest adventure!'", "image_prompt": "happy cartoon bunny sitting among giant lollipops smiling", "voice": "character"},
            {"text": "A friendly dragon offered to share his sparkling treasure chest.", "image_prompt": "cute cartoon dragon with open treasure chest, colorful", "voice": "narrator"},
            {"text": "Together they shared candy treasures and became best friends!", "image_prompt": "cartoon bunny and dragon celebrating friendship, vibrant colors", "voice": "narrator"},
        ],
    },
    "horror_short": {
        "title": "The Mirror That Screams",
        "scenes": [
            {"text": "She found an old mirror at the antique shop. The price tag read: FREE. Take it.", "image_prompt": "dark antique shop with a glowing cracked mirror", "voice": "narrator"},
            {"text": "That night, shadows moved behind the glass even when she stood still.", "image_prompt": "woman staring at mirror with shifting shadow behind glass", "voice": "narrator"},
            {"text": "'Who are you?' she whispered. The mirror whispered back her name.", "image_prompt": "close-up terrified woman face reflected in cracked mirror", "voice": "character"},
            {"text": "At 3 AM she woke to shattering glass — but the mirror was completely unbroken.", "image_prompt": "bedroom at night with intact mirror, broken glass on floor", "voice": "narrator"},
            {"text": "Written in fog on the glass: 'You're not the one who's trapped.'", "image_prompt": "mirror with fog message in dark room, horror film grain effect", "voice": "narrator"},
        ],
    },
    "motivational_story": {
        "title": "The Last Mile",
        "scenes": [
            {"text": "She had failed the exam three times. On attempt four, she almost quit.", "image_prompt": "determined woman standing outside exam hall, warm light", "voice": "narrator"},
            {"text": "Every failure and sleepless night had built her into this moment.", "image_prompt": "study montage collage, notebooks, inspirational lighting", "voice": "narrator"},
            {"text": "'I didn't come this far just to come this far,' she told her reflection.", "image_prompt": "close-up of woman's determined eyes, warm cinematic lighting", "voice": "character"},
            {"text": "She walked in and wrote every answer she had fought to learn.", "image_prompt": "confident woman writing exam at desk, calm focus", "voice": "narrator"},
            {"text": "The results came thirty days later. She had topped the class.", "image_prompt": "woman holding certificate triumphantly, uplifting atmosphere", "voice": "narrator"},
        ],
    },
    "comedy_sketch": {
        "title": "The World's Worst GPS",
        "scenes": [
            {"text": "Dave's GPS confidently announced: 'Turn left now' — into the ocean.", "image_prompt": "cartoon man driving toward ocean cliff following GPS", "voice": "narrator"},
            {"text": "'Recalculating,' it insisted, directing him into a cow pasture.", "image_prompt": "cartoon car surrounded by confused cows in green field", "voice": "character"},
            {"text": "His destination? The grocery store. Three detours later, another country.", "image_prompt": "cartoon map with hilariously absurd zigzag route", "voice": "narrator"},
            {"text": "A cow got in his car. The GPS said: 'New passenger detected. Five stars.'", "image_prompt": "cartoon man and cow sitting in car together, GPS", "voice": "narrator"},
            {"text": "He arrived at the wrong store. But the cow bought everything he needed.", "image_prompt": "happy cartoon cow at checkout counter, man facepalming", "voice": "narrator"},
        ],
    },
}

def _get_dry_run_story(category: Category, chapter: int) -> StoryOutput:
    data = _DRY_RUN_STORIES.get(category.value, _DRY_RUN_STORIES["motivational_story"])
    title = data["title"]
    if chapter > 1:
        title = f"{title} — Chapter {chapter}"
    scenes = [
        Scene(text=s["text"], image_prompt=s["image_prompt"], voice=VoiceType(s["voice"]))
        for s in data["scenes"]
    ]
    logger.info("[DRY_RUN] Returning placeholder story: '%s'", title)
    return StoryOutput(title=title, scenes=scenes)

def _load_pipeline(model_name: str) -> Any:
    from transformers import pipeline as hf_pipeline
    logger.info("Loading LLM: %s (CPU mode) — this may take a few minutes…", model_name)
    pipe = hf_pipeline("text-generation", model=model_name, device=-1, token=config.HF_TOKEN or None, torch_dtype="auto")
    logger.info("LLM loaded: %s", model_name)
    return pipe

def _get_pipeline() -> Any:
    global _pipeline, _loaded_model_name
    if _pipeline is not None:
        return _pipeline
    for model_name in (config.LLM_MODEL_PRIMARY, config.LLM_MODEL_FALLBACK):
        try:
            _pipeline = _load_pipeline(model_name)
            _loaded_model_name = model_name
            return _pipeline
        except Exception as exc:
            logger.warning("Failed to load '%s': %s. Trying fallback…", model_name, exc)
    raise RuntimeError("No LLM loaded. Set DRY_RUN=1 or check HF_TOKEN/network.")

def _build_prompt(category: Category, previous_summary: str, chapter: int) -> str:
    continuation = f"\nChapter {chapter}. Past: {previous_summary[:200]}\n" if previous_summary else ""
    cat_label = category.value.replace("_", " ").title()
    return f"""<|system|>
You are a JSON-only storytelling bot.
</s>
<|user|>
Category: {cat_label}{continuation}
Write {config.MAX_SCENES} short scenes. Return ONLY JSON.
{{
  "title": "catchy title",
  "scenes": [
    {{"text": "narration", "image_prompt": "SD prompt", "voice": "narrator"}}
  ]
}}
</s>
<|assistant|>
"""

def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not extract valid JSON from:\n{raw[:500]}")

class StoryService:
    def generate(self, category: Category, memory: EpisodeMemory | None = None) -> StoryOutput:
        prev_summary = memory.summary if memory else ""
        chapter = memory.chapter if memory else 1
        
        if config.DRY_RUN:
            return _get_dry_run_story(category, chapter)
            
        prompt = _build_prompt(category, prev_summary, chapter)
        logger.info("Generating story | category=%s | chapter=%d", category.value, chapter)
        
        pipe = _get_pipeline()
        try:
            result = pipe(prompt, max_new_tokens=config.LLM_MAX_NEW_TOKENS, temperature=config.LLM_TEMPERATURE, do_sample=True, return_full_text=False)
            raw_text = result[0]["generated_text"]
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            if config.DRY_RUN: 
                return _get_dry_run_story(category, chapter)
            raise RuntimeError(f"Story generation failed: {exc}") from exc

        try:
            data = _extract_json(raw_text)
            scenes = [Scene(text=str(s.get("text", "")).strip(), image_prompt=str(s.get("image_prompt", "")).strip(), voice=VoiceType(s.get("voice", "narrator"))) for s in data.get("scenes", [])]
            return StoryOutput(title=str(data.get("title", "Untitled")), scenes=scenes)
        except Exception as exc:
            logger.error("JSON parsing failed, returning fallback story: %s", exc)
            return _get_dry_run_story(category, chapter)



