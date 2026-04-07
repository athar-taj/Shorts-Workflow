"""
Service – Google Veo (Flow) AI Video Generation.

Replaces Pexels stock footage with AI-generated cinematic clips.

Features:
1. Smart prompt engineering per category (maps CATEGORY_MAP → cinematic style)
2. Scene-aware prompt builder using script's scene_hints + pexels_queries
3. Polling loop with configurable timeout
4. Fallback to Pexels if Veo fails / quota exceeded
5. Saves clips to the same tmp_dir as Pexels clips (fully compatible with FFmpeg assembler)
"""

import os
import re
import time
import urllib.request
import urllib.error

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("service.veo")

# ---------------------------------------------------------------------------
# VEO MODEL CONFIG
# ---------------------------------------------------------------------------
VEO_MODEL = "veo-3.1-fast-generate-preview"   # fast preview tier (no audio)
VEO3_MODEL = "veo-3-0-generate-preview"        # Veo 3 full — supports native audio
VEO_ASPECT_RATIO = "9:16"                      # portrait = Shorts native
VEO_POLL_INTERVAL_SEC = 15
VEO_MAX_WAIT_SEC = 420   # 7 min hard cap — Veo 3 with audio can take longer


# ---------------------------------------------------------------------------
# CATEGORY → CINEMATIC STYLE MAPPING
# Each entry controls: camera work, lighting, mood, post-processing look.
# These are appended to EVERY prompt so Veo stays consistent per category.
# ---------------------------------------------------------------------------
CATEGORY_CINEMATIC_STYLE: dict[str, str] = {
    "Gaming & Metaverse": (
        "shot on Sony A7S III, dynamic handheld motion, high-contrast RGB gaming setup lighting, "
        "dark room with neon glow, tight close-ups on hands and screens, 24fps cinematic look, "
        "lens flares, bokeh background with gaming peripherals"
    ),
    "Cooking & Gastronomy": (
        "overhead 4K food photography style, warm golden natural light, shallow depth of field, "
        "steam wisps, rich saturated colours, slow-motion pour or chop moments, clean wooden surfaces, "
        "cinematic food film aesthetic"
    ),
    "Comedy & Entertainment": (
        "bright vlog-style lighting, energetic handheld shaky cam, exaggerated reaction close-ups, "
        "vibrant colours, fast zoom-ins, casual indoor setting with personality-driven composition"
    ),
    "Geopolitics, War & Defense": (
        "documentary-style cinematography, desaturated colour grade (teal and orange), "
        "slow push-in on maps or military equipment, dramatic chiaroscuro lighting, "
        "handheld realism, dust and atmosphere, cinematic 2.39:1 widescreen feel even in portrait"
    ),
    "Facts & Infotainment": (
        "clean minimalist studio background, soft diffused LED lighting, smooth gimbal-stabilised motion, "
        "punchy graphic overlays implied by tight framing, hyper-clear 4K detail, professional talking-head framing"
    ),
    "Tech & Future-Proofing": (
        "sleek corporate-tech aesthetic, cool blue and white lighting, product close-ups with bokeh, "
        "modern workspace environment, macro lens detail shots, smooth camera movements, "
        "clean desk setup with glowing screens"
    ),
    "AI & Automation": (
        "futuristic digital aesthetic, holographic blue glow, dark background with data-stream particles, "
        "smooth dolly moves across glowing servers or monitors, cinematic sci-fi lighting, "
        "shallow DOF with sharp foreground elements"
    ),
    "Earning, Finance & Side Hustles": (
        "aspirational lifestyle cinematography, warm golden hour light, "
        "overhead laptop and coffee aesthetic, clean modern desk environment, "
        "motivational yet grounded visual tone, smooth tracking shots"
    ),
    "Lifestyle & POV": (
        "first-person POV handheld, golden hour natural light, travel vlog colour grade (warm & vivid), "
        "candid emotional moments, shallow depth of field portraits, "
        "cinematic lifestyle film look"
    ),
    "Automotive & Racing": (
        "cinematic car chase perspective, low-angle tracking shots, motion blur on wheels, "
        "golden hour backlight, dramatic sky, slow-motion acceleration detail, "
        "high-contrast punchy colour grade"
    ),
    "Health, Fitness & Sports": (
        "high-energy sports cinematography, bright gym or outdoor lighting, "
        "slow-motion muscle-flex or sprint moments, motivational warm colour grade, "
        "dynamic tracking alongside athlete, close-ups on form and expression"
    ),
    "Relationships & Social Skills": (
        "warm intimate cinematography, soft bokeh backgrounds, natural window light, "
        "genuine emotional close-ups, cosy indoor settings, "
        "documentary realism with a warm colour grade"
    ),
    "Education & Study": (
        "bright classroom or desk aesthetic, clean organised study setup, "
        "overhead stationery and notebook shots, focused student close-ups, "
        "soft neutral lighting, motivating and energetic visual tone"
    ),
    "Career & Corporate": (
        "modern corporate office environment, professional window light, "
        "sleek desk setup, confident professional framing, "
        "cool-neutral colour grade, smooth gimbal motion"
    ),
    "Business & Marketing": (
        "premium brand-video aesthetic, dramatic directional lighting, "
        "clean white-and-black composition, boardroom or city-skyline context, "
        "confident wide-to-close camera moves, cinematic business film look"
    ),
    "Self Improvement & Mindset": (
        "sunrise outdoor cinematography, warm motivational colour grade, "
        "lone figure in expansive landscape, slow contemplative pans, "
        "soft yet purposeful lighting, cinematic personal-growth film aesthetic"
    ),
    "Productivity & Tools": (
        "clean flat-lay desk with organised tools, crisp natural side-lighting, "
        "satisfying macro close-ups on apps and hands, "
        "smooth overhead pan, minimalist aesthetic"
    ),
    "History (Short Storytelling)": (
        "cinematic historical documentary style, desaturated film-grain look, "
        "dramatic chiaroscuro lighting, slow push-in on ancient textures or maps, "
        "cinematic 1.85:1 composition even in portrait, emotive orchestral visual pacing"
    ),
    "Science & Engineering": (
        "Kurzgesagt-inspired visual clarity, clean high-contrast lighting, "
        "macro scientific detail shots, smooth camera reveals, "
        "vibrant but grounded colour palette, professional science-documentary cinematography"
    ),
    "True Crime (SFW) & Mystery": (
        "suspenseful noir-style cinematography, heavy shadows with single directional light, "
        "slow push-ins that build tension, desaturated high-contrast look, "
        "moody atmospheric colour grade, documentary realism"
    ),
    "Scams, Safety & Consumer Awareness": (
        "urgent alert visual style, high-contrast warning aesthetics, "
        "smartphone screen close-ups, concerned person reaction shots, "
        "dramatic split-lighting, clear and informative framing"
    ),
    "Movies, Web Series & Anime": (
        "cinematic film-review aesthetic, warm home-cinema lighting, "
        "sofa and screen environment, passionate fan close-ups, "
        "warm orange-and-blue colour grade, movie-poster-level composition"
    ),
    "Mental Health & Emotional Intelligence": (
        "soft, safe, desaturated-warm cinematography, gentle natural light, "
        "introspective close-ups on face and hands, calm indoor environments, "
        "meditative slow camera motion, empathetic visual tone"
    ),
    "Motivation & Inspiration (Story Format)": (
        "cinematic underdog visual storytelling, golden backlight, "
        "dramatic low-angle hero shots, slow-motion personal triumph moments, "
        "emotional warm colour grade, documentary realism blended with inspiration"
    ),
    # Fallback for any unknown category
    "_default": (
        "cinematic portrait shot, professional lighting, 4K detail, "
        "smooth camera movement, shallow depth of field, realistic textures, "
        "modern aesthetic, high production value"
    ),
}


# ---------------------------------------------------------------------------
# SCENE TYPE → SHOT STYLE
# Maps common scene_hint keywords to specific camera/shot instructions.
# ---------------------------------------------------------------------------
SCENE_SHOT_OVERRIDES: list[tuple[str, str]] = [
    # (keyword_in_hint, shot_description)
    ("hook",        "extreme close-up on subject's face showing intense curiosity or shock"),
    ("face",        "tight close-up on face, authentic emotion, sharp eyes in focus"),
    ("hand",        "macro close-up on hands interacting with object, smooth motion"),
    ("screen",      "tight shot of glowing monitor screen reflecting on subject's face"),
    ("office",      "wide establishing shot of modern corporate office environment"),
    ("outdoor",     "wide handheld shot of outdoor environment, natural light, atmospheric"),
    ("crowd",       "slow-motion wide shot of diverse crowd, bokeh depth, energy"),
    ("phone",       "extreme close-up of smartphone screen with subject reacting"),
    ("think",       "medium shot of person in contemplation, slow push-in, soft light"),
    ("react",       "subject reacts with surprise, handheld medium shot, authentic emotion"),
    ("reveal",      "slow camera pull-back or dolly revealing something unexpected"),
    ("cta",         "direct to camera confident close-up, warm light, inviting expression"),
    ("fact",        "clean minimal shot with floating text space implied by framing"),
    ("twist",       "quick whip-pan followed by tight close-up, dynamic and surprising"),
    ("walk",        "tracking alongside walking subject, smooth gimbal, environment blur"),
    ("city",        "sweeping aerial-style tilt down to street level, golden hour city light"),
    ("money",       "overhead close-up of hands counting notes or using laptop for trading"),
    ("code",        "close-up of code on monitor, blue glow on programmer's focused face"),
    ("food",        "overhead slow-motion food preparation, steam and vibrant colours"),
    ("gym",         "slow-motion compound lift in gym, dramatic side lighting, intensity"),
    ("nature",      "cinematic landscape reveal, sunrise light, smooth drone-like glide"),
    ("book",        "overhead macro of open book pages with hand turning, warm light"),
    ("laugh",       "genuine laughter close-up, warm natural light, candid feel"),
    ("serious",     "intense direct look to camera, dark dramatic lighting, slow push-in"),
    ("confused",    "subject looks confused then understands, medium shot, authentic"),
    ("success",     "triumphant low-angle shot, warm backlight, slow-motion celebration"),
    ("frustrated",  "close-up of frustrated person running hands through hair, blue monitor glow"),
    ("dark",        "dimly lit atmospheric scene, single practical light source, noir feel"),
    ("bright",      "high-key bright studio or outdoor scene, clean and optimistic"),
]


# ---------------------------------------------------------------------------
# PROMPT BUILDER
# ---------------------------------------------------------------------------

def build_veo_prompt(
    scene_hint: str,
    pexels_query: str,
    category: str,
    script_topic: str = "",
    scene_index: int = 0,
    total_scenes: int = 1,
) -> str:
    """
    Builds a rich, production-quality Veo prompt for a single scene.

    Parameters
    ----------
    scene_hint      : Free-text from script's scene_hints (e.g. "Developer frustrated at code")
    pexels_query    : Search query from pexels_queries (e.g. "frustrated developer office night")
    category        : CATEGORY_MAP key (e.g. "Tech & Future-Proofing")
    script_topic    : The video topic for context grounding
    scene_index     : 0-based scene index
    total_scenes    : Total number of scenes
    """

    # 1. Determine shot type from scene hint keywords
    shot_override = ""
    hint_lower = (scene_hint + " " + pexels_query).lower()
    for keyword, shot_desc in SCENE_SHOT_OVERRIDES:
        if keyword in hint_lower:
            shot_override = shot_desc
            break

    # 2. Get category cinematic style
    style = CATEGORY_CINEMATIC_STYLE.get(category, CATEGORY_CINEMATIC_STYLE["_default"])

    # 3. Determine scene position tag (pacing)
    if scene_index == 0:
        position_note = "opening hook scene — immediately grabs attention"
    elif scene_index == total_scenes - 1:
        position_note = "closing call-to-action scene — warm, inviting, direct"
    else:
        position_note = "mid-video build scene — engaging and informative"

    # 4. Build the core subject description from scene_hint
    # Clean up common AI-generated phrases for a cleaner prompt
    subject = re.sub(r"\b(scene|shot|visual|showing|depict|display)\b", "", scene_hint, flags=re.IGNORECASE).strip()
    subject = subject.strip(".,;:-").strip()
    if not subject:
        subject = pexels_query

    # 5. Assemble final prompt
    parts = []

    # Shot style (override or generic medium shot)
    if shot_override:
        parts.append(f"A {shot_override}")
    else:
        parts.append(f"A cinematic medium shot of {subject.lower()}")

    # Topic grounding (only if provided)
    if script_topic:
        parts.append(f"related to {script_topic}")

    # Role in video
    parts.append(f"({position_note})")

    # Category cinematic style
    parts.append(style)

    # Universal quality tags
    parts.append(
        "No text overlays. No subtitles. No watermarks. "
        "Photorealistic. Smooth motion. 4K quality. "
        "Professional production value. "
        "Portrait orientation 9:16, suitable for YouTube Shorts."
    )

    return ". ".join(parts)


# ---------------------------------------------------------------------------
# PRE-BAKED PROMPT LIBRARY (category-level safe fallbacks)
# These fire when scene_hints are generic or missing.
# ---------------------------------------------------------------------------

CATEGORY_FALLBACK_PROMPTS: dict[str, list[str]] = {
    "Tech & Future-Proofing": [
        (
            "Cinematic close-up of a software developer in a dimly lit modern corporate office at night, "
            "hunched over dual monitors filled with code. Blue monitor glow illuminates their focused, intense face. "
            "Background office is out-of-focus with bokeh from distant monitors. "
            "4K, shallow depth of field, photorealistic, portrait 9:16."
        ),
        (
            "Medium shot of a tech professional typing rapidly on a mechanical keyboard, "
            "then leaning back to study the screen with analytical intensity. "
            "Sleek modern desk setup with soft ambient lighting, cable management visible. "
            "Smooth gimbal motion, 4K, cinematic tech aesthetic, portrait 9:16."
        ),
        (
            "Close-up of glowing smartphone screen with cutting-edge UI animations, "
            "held by hands with sharp foreground focus and blurred futuristic office background. "
            "Cool blue-white lighting, premium product cinematography, portrait 9:16."
        ),
    ],
    "AI & Automation": [
        (
            "Cinematic shot of a person interacting with a glowing holographic AI interface in a dark room, "
            "blue data streams floating around them, face illuminated by the light of the display. "
            "Futuristic sci-fi aesthetic, smooth camera push-in, 4K, portrait 9:16."
        ),
        (
            "Wide shot of a server room with rows of blinking LED lights, "
            "camera gliding slowly through the corridor, atmospheric cool-blue lighting. "
            "Documentary-style cinematography, depth and scale, portrait 9:16."
        ),
    ],
    "Gaming & Metaverse": [
        (
            "Dynamic close-up of a gamer's hands on a mechanical keyboard and mouse, "
            "RGB lighting cascading across the scene, intense focus on screen reflection in their eyes. "
            "High-contrast gaming room lighting, cinematic 24fps look, portrait 9:16."
        ),
        (
            "Medium shot of an excited gamer celebrating a win, fists raised, big genuine reaction. "
            "Gaming setup in background with glowing screens, energy and personality. "
            "Vibrant and dynamic, handheld motion, portrait 9:16."
        ),
    ],
    "Self Improvement & Mindset": [
        (
            "Cinematic wide shot of a lone person standing at sunrise on a hilltop, "
            "golden backlight creating a silhouette, slow camera pan, motivational atmosphere. "
            "Warm colour grade, 4K, smooth motion, portrait 9:16."
        ),
    ],
    "Earning, Finance & Side Hustles": [
        (
            "Overhead shot of a person working on a laptop at a clean modern desk, "
            "coffee cup and notebook beside them, soft morning window light, "
            "aspirational and focused mood, warm colour grade, portrait 9:16."
        ),
    ],
    "Health, Fitness & Sports": [
        (
            "Slow-motion cinematic shot of an athlete performing a powerful deadlift in a modern gym, "
            "dramatic side lighting highlighting muscle definition, intense focused expression. "
            "High-energy sports cinematography, warm motivational grade, portrait 9:16."
        ),
    ],
    "Facts & Infotainment": [
        (
            "Clean professional talking-head framing of a young Indian presenter in a minimal studio, "
            "soft LED lighting, sharp focus, neutral background that conveys authority and approachability. "
            "4K, smooth camera, portrait 9:16."
        ),
    ],
    "Career & Corporate": [
        (
            "Cinematic medium shot of a confident professional in a modern office, "
            "window light casting soft shadows, reviewing documents at a sleek desk. "
            "Cool-neutral colour grade, professional composition, portrait 9:16."
        ),
        (
            "Close-up of a corporate worker staring intensely at their monitor, visibly frustrated, "
            "running hands through hair, heavy sigh visible. "
            "Blue glow from screen, empty blurred office background. "
            "4K, high detail, realistic textures, portrait 9:16."
        ),
    ],
    "_default": [
        (
            "Cinematic wide shot of a young Indian professional in a modern urban setting, "
            "golden hour light, confident and purposeful expression, smooth tracking camera motion. "
            "4K, shallow depth of field, premium production value, portrait 9:16."
        ),
    ],
}


def get_fallback_prompt(category: str, scene_index: int = 0) -> str:
    """Returns a pre-baked cinematic prompt for a category, cycling by scene index."""
    prompts = CATEGORY_FALLBACK_PROMPTS.get(category, CATEGORY_FALLBACK_PROMPTS["_default"])
    return prompts[scene_index % len(prompts)]


# ---------------------------------------------------------------------------
# VEO CLIENT SERVICE
# ---------------------------------------------------------------------------

class VeoService:
    """
    Wraps Google Veo video generation via the google-genai SDK.

    Usage:
        svc = VeoService()
        clip_path = svc.generate_clip(
            scene_hint="Developer frustrated at code",
            pexels_query="frustrated developer office night",
            category="Tech & Future-Proofing",
            script_topic="Why developers get frustrated",
            scene_index=0,
            total_scenes=3,
            out_path="/tmp/videos/scene_1.mp4"
        )
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or getattr(settings, "google_genai_api_key", None)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                if not self.api_key:
                    raise ValueError(
                        "google_genai_api_key is not set. "
                        "Add GOOGLE_GENAI_API_KEY to your .env file."
                    )
                self._client = genai.Client(api_key=self.api_key)
                log.info("Google GenAI client initialised (Veo).")
            except ImportError:
                raise ImportError(
                    "google-genai package not installed. "
                    "Run: pip install google-genai"
                )
        return self._client

    def generate_clip(
        self,
        scene_hint: str,
        pexels_query: str,
        category: str,
        script_topic: str = "",
        scene_index: int = 0,
        total_scenes: int = 1,
        out_path: str | None = None,
        use_fallback_prompt: bool = False,
        custom_prompt: str | None = None,
    ) -> str | None:
        """
        Generates a single video clip via Veo and saves it to out_path.

        Returns the absolute path to the saved .mp4, or None on failure.
        """
        # Build prompt
        if custom_prompt:
            prompt = custom_prompt
        elif use_fallback_prompt:
            prompt = get_fallback_prompt(category, scene_index)
        else:
            prompt = build_veo_prompt(
                scene_hint=scene_hint,
                pexels_query=pexels_query,
                category=category,
                script_topic=script_topic,
                scene_index=scene_index,
                total_scenes=total_scenes,
            )

        log.info(
            "🎬 [Veo] Scene %d/%d | Category: %s\n  Prompt: %s",
            scene_index + 1, total_scenes, category, prompt[:200]
        )

        if not out_path:
            os.makedirs(settings.tmp_dir, exist_ok=True)
            out_path = os.path.join(settings.tmp_dir, f"veo_scene_{scene_index + 1}.mp4")

        try:
            from google.genai import types

            client = self._get_client()

            # Trigger generation
            operation = client.models.generate_videos(
                model=VEO_MODEL,
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio=VEO_ASPECT_RATIO,
                    # generate_audio=False  # no audio — we overlay TTS
                ),
            )

            # Poll until done
            elapsed = 0
            while not operation.done:
                if elapsed >= VEO_MAX_WAIT_SEC:
                    log.error("[Veo] Scene %d timed out after %ds.", scene_index + 1, VEO_MAX_WAIT_SEC)
                    return None
                log.info("[Veo] Scene %d still generating... (%ds elapsed)", scene_index + 1, elapsed)
                time.sleep(VEO_POLL_INTERVAL_SEC)
                elapsed += VEO_POLL_INTERVAL_SEC
                operation = client.operations.get(operation)

            if not operation.result:
                log.error("[Veo] Scene %d generation returned no result.", scene_index + 1)
                return None

            # Download the video
            generated = operation.result.generated_videos
            if not generated:
                log.error("[Veo] Scene %d: generated_videos list is empty.", scene_index + 1)
                return None

            video_obj = generated[0].video
            video_uri = getattr(video_obj, "uri", None)

            if video_uri:
                # URI mode: download via HTTP
                log.info("[Veo] Scene %d ready. Downloading from URI...", scene_index + 1)
                urllib.request.urlretrieve(video_uri, out_path)
                log.info("[Veo] Scene %d saved → %s", scene_index + 1, out_path)
                return out_path
            else:
                # Inline bytes mode
                video_bytes = getattr(video_obj, "video_bytes", None) or getattr(video_obj, "bytes", None)
                if video_bytes:
                    with open(out_path, "wb") as f:
                        f.write(video_bytes)
                    log.info("[Veo] Scene %d saved (inline bytes) → %s", scene_index + 1, out_path)
                    return out_path
                else:
                    log.error("[Veo] Scene %d: no URI or bytes available.", scene_index + 1)
                    return None

        except Exception as e:
            log.error("[Veo] Scene %d failed: %s", scene_index + 1, e)
            return None

    def generate_clips_for_scenes(
        self,
        scenes: list[dict],
        category: str,
        script_topic: str = "",
        fallback_to_pexels: bool = True,
    ) -> list[str]:
        """
        Generates Veo clips for ALL scenes in the script.
        If Veo fails for a scene and fallback_to_pexels=True,
        it will attempt to download from Pexels instead.

        Parameters
        ----------
        scenes          : list from workflow.breakdown_scenes() or script["scene_hints"]
        category        : CATEGORY_MAP category string
        script_topic    : Topic from script brief
        fallback_to_pexels : Fall back to Pexels on failure

        Returns list of absolute paths to video clips (same contract as fetch_visuals).
        """
        total = len(scenes)
        clip_paths: list[str] = []

        os.makedirs(settings.tmp_dir, exist_ok=True)

        for i, scene in enumerate(scenes):
            # Support both scene dict format (from breakdown_scenes) and plain string (from scene_hints list)
            if isinstance(scene, dict):
                scene_hint = scene.get("keyword") or scene.get("text") or ""
                pexels_query = scene.get("keyword") or ""
            else:
                scene_hint = str(scene)
                pexels_query = str(scene)

            out_path = os.path.join(settings.tmp_dir, f"scene_{i + 1}.mp4")
            saved = self.generate_clip(
                scene_hint=scene_hint,
                pexels_query=pexels_query,
                category=category,
                script_topic=script_topic,
                scene_index=i,
                total_scenes=total,
                out_path=out_path,
            )

            if saved:
                clip_paths.append(saved)
            elif fallback_to_pexels:
                log.warning("[Veo] Scene %d failed. Falling back to Pexels...", i + 1)
                pexels_path = self._pexels_fallback(pexels_query or scene_hint, i, out_path)
                if pexels_path:
                    clip_paths.append(pexels_path)
                else:
                    log.error("[Veo] Scene %d: Pexels fallback also failed. Skipping.", i + 1)
            else:
                log.error("[Veo] Scene %d: Veo failed and no fallback. Skipping.", i + 1)

        log.info("[Veo] Generated %d/%d clips.", len(clip_paths), total)
        return clip_paths

    def _pexels_fallback(self, keyword: str, scene_index: int, out_path: str) -> str | None:
        """Minimal Pexels single-clip downloader for fallback use."""
        try:
            import requests
            session = requests.Session()
            session.headers.update({
                "Authorization": settings.pexels_api_key,
                "User-Agent": "Mozilla/5.0",
            })
            resp = session.get(
                "https://api.pexels.com/videos/search",
                params={"query": keyword, "per_page": 5, "orientation": "portrait"},
                timeout=15,
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            if not videos:
                return None

            video_files = videos[0].get("video_files", [])
            video_files.sort(key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
            if not video_files:
                return None

            url = video_files[0]["link"]
            with session.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            log.info("[Pexels fallback] Scene %d saved → %s", scene_index + 1, out_path)
            return out_path
        except Exception as e:
            log.error("[Pexels fallback] Scene %d failed: %s", scene_index + 1, e)
            return None

    # -----------------------------------------------------------------------
    # STANDALONE: Generate a single video from a raw user prompt (with audio)
    # -----------------------------------------------------------------------

    def generate_video_from_prompt(
        self,
        prompt: str,
        out_path: str | None = None,
        aspect_ratio: str = "9:16",
        generate_audio: bool = True,
        duration_seconds: int | None = None,
    ) -> str | None:
        """
        Generate a single Veo 3 video from a raw user-supplied prompt.

        Veo 3 (veo-3-0-generate-preview) natively generates synchronized
        audio (ambient sound / music / sound effects) alongside the video
        when generate_audio=True.

        Parameters
        ----------
        prompt          : Free-text prompt describing what to generate.
        out_path        : Where to save the .mp4 (auto-generated if None).
        aspect_ratio    : "9:16" (Shorts portrait) or "16:9" or "1:1".
        generate_audio  : Pass True to enable Veo 3 native audio generation.
        duration_seconds: Optional clip length hint (model may ignore).

        Returns
        -------
        Absolute path to the saved .mp4, or None on failure.
        """
        if not prompt or not prompt.strip():
            log.error("[Veo3] generate_video_from_prompt called with empty prompt.")
            return None

        if not out_path:
            os.makedirs(settings.tmp_dir, exist_ok=True)
            import time as _time
            ts = int(_time.time())
            out_path = os.path.join(settings.tmp_dir, f"veo3_generated_{ts}.mp4")

        audio_tag = "🔊 with audio" if generate_audio else "🔇 silent"
        log.info(
            "🎬 [Veo3] Generating video %s\n  Model: %s\n  Aspect: %s\n  Prompt: %s",
            audio_tag, VEO3_MODEL, aspect_ratio, prompt[:300],
        )

        try:
            from google.genai import types

            client = self._get_client()

            # Build config — only pass duration if caller specified it
            config_kwargs: dict = {
                "aspect_ratio": aspect_ratio,
                "generate_audio": generate_audio,
            }
            if duration_seconds and duration_seconds > 0:
                config_kwargs["duration_seconds"] = duration_seconds

            operation = client.models.generate_videos(
                model=VEO3_MODEL,
                prompt=prompt,
                config=types.GenerateVideosConfig(**config_kwargs),
            )

            # Poll until done
            elapsed = 0
            while not operation.done:
                if elapsed >= VEO_MAX_WAIT_SEC:
                    log.error(
                        "[Veo3] Generation timed out after %ds. "
                        "Try a simpler prompt or reduce duration.",
                        VEO_MAX_WAIT_SEC,
                    )
                    return None
                log.info(
                    "[Veo3] Still generating... (%ds elapsed, checking every %ds)",
                    elapsed, VEO_POLL_INTERVAL_SEC,
                )
                time.sleep(VEO_POLL_INTERVAL_SEC)
                elapsed += VEO_POLL_INTERVAL_SEC
                operation = client.operations.get(operation)

            if not operation.result:
                log.error("[Veo3] Generation returned no result.")
                return None

            generated = operation.result.generated_videos
            if not generated:
                log.error("[Veo3] generated_videos list is empty.")
                return None

            video_obj = generated[0].video
            video_uri = getattr(video_obj, "uri", None)

            if video_uri:
                log.info("[Veo3] Video ready. Downloading from URI...")
                urllib.request.urlretrieve(video_uri, out_path)
                log.info("[Veo3] Saved → %s", out_path)
                return out_path
            else:
                video_bytes = (
                    getattr(video_obj, "video_bytes", None)
                    or getattr(video_obj, "bytes", None)
                )
                if video_bytes:
                    with open(out_path, "wb") as f:
                        f.write(video_bytes)
                    log.info("[Veo3] Saved (inline bytes) → %s", out_path)
                    return out_path
                else:
                    log.error("[Veo3] No URI or bytes in the response.")
                    return None

        except Exception as e:
            log.error("[Veo3] generate_video_from_prompt failed: %s", e)
            return None


# ---------------------------------------------------------------------------
# CONVENIENCE: build prompt from a v3 script JSON (scene_hints + pexels_queries)
# ---------------------------------------------------------------------------

def prompts_from_script(script: dict, category: str) -> list[dict]:
    """
    Given a script dict (from generate_short_v3 or generate_script_v2_json),
    returns a list of dicts:
        [{
            "scene_index": 0,
            "scene_hint": "...",
            "pexels_query": "...",
            "veo_prompt": "Full Veo prompt string",
        }, ...]

    Useful for previewing / logging prompts before actual generation.
    """
    scene_hints: list = script.get("scene_hints") or []
    pexels_queries: list = script.get("pexels_queries") or []
    topic: str = (script.get("_meta") or {}).get("topic") or ""
    total = max(len(scene_hints), len(pexels_queries), 1)

    results = []
    for i in range(total):
        hint = scene_hints[i] if i < len(scene_hints) else ""
        query = pexels_queries[i] if i < len(pexels_queries) else hint
        prompt = build_veo_prompt(
            scene_hint=hint,
            pexels_query=query,
            category=category,
            script_topic=topic,
            scene_index=i,
            total_scenes=total,
        )
        results.append({
            "scene_index": i,
            "scene_hint": hint,
            "pexels_query": query,
            "veo_prompt": prompt,
        })
    return results
