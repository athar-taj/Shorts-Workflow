"""
Application configuration.

All tuneable knobs live here. Override via environment variables.
Example:
    set TMP_DIR=D:\\my_videos         # Windows
    export TMP_DIR=/data/videos       # Linux/Mac
    export DEFAULT_WHISPER_MODEL=small
    export DEFAULT_CLIP_DURATION=90
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Root of the project — the directory that contains this config.py's parent (app/)
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default storage folder: <project_root>/videos/
_DEFAULT_VIDEOS_DIR: str = os.path.join(PROJECT_ROOT, "videos")
os.makedirs(_DEFAULT_VIDEOS_DIR, exist_ok=True)   # create on import

# Default memes folder: <project_root>/assets/memes/
_DEFAULT_MEMES_DIR: str = os.path.join(PROJECT_ROOT, "assets", "memes")
os.makedirs(_DEFAULT_MEMES_DIR, exist_ok=True)    # create on import


class Settings(BaseSettings):
    """
    Reads values from environment variables (case-insensitive).
    Falls back to the defaults defined here.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Server ────────────────────────────────────────────────────────────────
    app_title: str = "YouTube Short Generator API"
    app_version: str = "2.0.0"
    app_description: str = (
        "Full local pipeline — Download → Crop (9:16) → Transcribe (Whisper) "
        "→ Burn Captions. Replaces Apify + SSH."
    )

    # ── File Storage ──────────────────────────────────────────────────────────
    # All pipeline files (downloads, crops, SRTs, final videos) are saved here.
    # Override via TMP_DIR env variable or .env file.
    tmp_dir: str = _DEFAULT_VIDEOS_DIR

    # ── Download ──────────────────────────────────────────────────────────────
    # Priority order:
    #   1. best pre-merged mp4 (no FFmpeg needed)          ← works without FFmpeg
    #   2. any pre-merged format                           ← works without FFmpeg
    #   3. video+audio merge (only if FFmpeg is installed) ← requires FFmpeg
    yt_format: str = "best[ext=mp4]/best"

    # ── Crop ──────────────────────────────────────────────────────────────────
    default_clip_duration: int = 60    # seconds
    default_start_sec: int = 0
    crop_target_width: int = 1080
    crop_target_height: int = 1920     # 9:16

    # ── FFmpeg ────────────────────────────────────────────────────────────────
    ffmpeg_preset: str = "fast"        # ultrafast | fast | medium | slow
    ffmpeg_crf: int = 23               # 0 (lossless) – 51 (worst)
    audio_bitrate: str = "128k"

    # ── Shorts style variation knobs ──────────────────────────────────────────
    # Avoid covering the center: keep overlays in safe zones.
    intro_blur_sec: float = 0.8        # 0 disables; small blur at the very start
    intro_zoom: bool = True            # subtle zoom-in effect (adds motion)

    # ── Background music tuning ───────────────────────────────────────────────
    bg_music_volume: float = 0.10      # 0.0–1.0 (music under voice)
    bg_music_tempo: float = 0.92       # <1.0 slower, >1.0 faster (0.5–2.0)
    bg_music_lowpass_hz: int = 9000    # soften harsh highs for “slow tune” feel

    # ── Memes / Stickers Overlay (local pack) ─────────────────────────────────
    # Put PNG/WebP/JPG stickers into: <project_root>/assets/memes/
    enable_memes: bool = True
    memes_dir: str = _DEFAULT_MEMES_DIR
    meme_overlay_start_sec: float = 2.0
    meme_overlay_end_sec: float = 5.5
    meme_overlay_width_px: int = 420   # sticker scale (keep readable, not huge)
    meme_overlay_margin_px: int = 36   # distance from edges

    # ── Whisper ───────────────────────────────────────────────────────────────
    default_whisper_model: str = "base"   # tiny | base | small | medium | large
    whisper_language: str = "en"

    # ── Caption style (FFmpeg force_style) ───────────────────────────────────
    caption_style: str = (
        "FontSize=12,"                  # Decreased font size for better aesthetics
        "PrimaryColour=&H0000FFFF,"     # Yellow color (Alpha, Blue, Green, Red)
        "OutlineColour=&H00000000,"
        "Bold=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=60"                    # Raise subtitles slightly above the bottom
    )

    # ── Headings ──────────────────────────────────────────────────────────────
    default_heading_text: str = "WAIT FOR IT..."

    # ── Integration Keys (From n8n) ──────────────────────────────────────────
    youtube_api_key: str = "AIzaSyC3NlYIRVlfG-t6K2ZtA3fI6j8DjffCrwo"
    openrouter_api_key: str = "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"
    telegram_bot_token: str = "8013291446:AAHR4Hp0DJAf0d4mvUAtt55EiJVicC4GzY4"
    telegram_chat_id: str = "1911134008"
    
    # ── AI API Keys (Generative Pipeline) ────────────────────────────────────
    elevenlabs_api_key: str = "sk_a30fd13ddea16cc154f23d945c627b2864ee23074d8b02af"
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM" # Rachel
    sarvam_api_key: str = "sk_v3jy1r18_g8vrJI6RQLUD0ZHSAabCrBtR"
    pexels_api_key: str = "uQiPGCUxiLP9mp2IgczfDJShTGQw4B7pL5EOvc6WvP2tgrdrTDe8j65L"

    # ── Google Veo (Flow) Video Generation ───────────────────────────────────
    # Get your API key from: https://aistudio.google.com/apikey
    # Add to .env:  GOOGLE_GENAI_API_KEY=your_key_here
    google_genai_api_key: str = ""  # empty = Veo disabled, falls back to Pexels

    # ── YouTube Config ───────────────────────────────────────────────────────
    yt_client_secrets_file: str = os.path.join(PROJECT_ROOT, "client_secret_2_954009129756-054jj7m94iomodinjik42raj3su0gnfh.apps.googleusercontent.com.json")
    yt_credentials_cache: str = os.path.join(PROJECT_ROOT, "youtube_token.json")

    # ── AI Shorts Generation (Transplanted) ──────────────────────────────────
    DRY_RUN: bool = False
    HF_TOKEN: str = "hf_dummy"
    LLM_BACKEND: str = "transformers"
    LLM_MODEL_PRIMARY: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    LLM_MODEL_FALLBACK: str = "sshleifer/tiny-gpt2"
    LLM_MAX_NEW_TOKENS: int = 600
    LLM_TEMPERATURE: float = 0.85
    IMAGE_MODEL_PRIMARY: str = "runwayml/stable-diffusion-v1-5"
    IMAGE_MODEL_FALLBACK: str = "CompVis/stable-diffusion-v1-4"
    IMAGE_RESOLUTION: tuple[int, int] = (512, 512)
    IMAGE_INFERENCE_STEPS: int = 4
    IMAGE_GUIDANCE_SCALE: float = 7.5
    IMAGE_FORMAT: str = "PNG"
    TTS_MODEL: str = "tts_models/en/ljspeech/tacotron2-DDC"
    TTS_SPEAKER_SPEED: float = 1.0
    TTS_SAMPLE_RATE: int = 22050
    MAX_SCENES: int = 5
    MAX_STORY_WORDS: int = 120
    MAX_SCENE_WORDS: int = 24
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920
    VIDEO_FPS: int = 24
    VIDEO_CODEC: str = "libx264"
    AUDIO_CODEC: str = "aac"
    SCENE_DURATION_S: float = 6.0
    ZOOM_SPEED: float = 0.0005
    CATEGORIES: list[str] = ["kids_fun_story", "horror_short", "motivational_story", "comedy_sketch"]
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = Path(os.path.join(PROJECT_ROOT, "pipeline.log"))
    OUTPUT_DIR: Path = Path(os.path.join(PROJECT_ROOT, "outputs"))
    MEMORY_DIR: Path = Path(os.path.join(PROJECT_ROOT, "memory"))
    AUDIO_DIR: Path = Path(os.path.join(PROJECT_ROOT, "outputs", "audio"))
    IMAGE_DIR: Path = Path(os.path.join(PROJECT_ROOT, "outputs", "images"))
    VIDEO_DIR: Path = Path(os.path.join(PROJECT_ROOT, "outputs", "videos"))


# Singleton – import this everywhere
settings = Settings()

# Ensure directories exist
for _d in [settings.OUTPUT_DIR, settings.MEMORY_DIR, settings.AUDIO_DIR, settings.IMAGE_DIR, settings.VIDEO_DIR]:
    os.makedirs(_d, exist_ok=True)

