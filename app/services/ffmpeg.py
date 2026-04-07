"""
Service – FFmpeg video processing.

Responsibilities:
  1. crop_to_vertical        – Convert horizontal → vertical (9:16), trim clip.
  2. burn_captions           – Burn SRT subtitles + random style overlays.
  3. combine_generative_video– Stitch clips + voice + optional BG music.
  4. apply_shorts_style      – Random style engine (4 variations).

FFmpeg must be installed and available on the system PATH.
"""

import os
import random
import shutil
import subprocess

from app.config import settings
from app.utils.ffmpeg_resolver import get_ffmpeg_binary
from app.utils.logger import get_logger

log = get_logger("service.ffmpeg")


def _run(cmd: list[str]) -> None:
    """
    Execute an FFmpeg command.

    Args:
        cmd: Full command list, starting with "ffmpeg".

    Raises:
        RuntimeError: On non-zero exit code, with the last 800 chars of stderr.
    """
    cmd[0] = get_ffmpeg_binary()   # resolve system or bundled binary
    log.info("FFmpeg ▶ %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("FFmpeg stderr:\n%s", result.stderr)
        raise RuntimeError(f"FFmpeg error: {result.stderr[-800:]}")


def _safe_text(text: str) -> str:
    """
    Strip FFmpeg drawtext-unsafe chars (:, ', \\, [, ]).
    Used only for plain drawtext calls (non-emoji text).
    """
    for bad in ["'", ":", "\\", "[", "]"]:
        text = text.replace(bad, "")
    return text.strip()


def _render_emoji_overlay(
    text: str,
    out_png: str,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    font_size: int = 60,
    text_color: tuple = (255, 255, 255, 255),
    box_color: tuple = (0, 0, 0, 180),
    box_padding: int = 22,
    y_pos: int | None = None,
) -> str:
    """
    Render text + full-color emoji onto a transparent PNG using Pillow.

    HOW IT WORKS:
    ─────────────
    FFmpeg's drawtext filter uses libfreetype which cannot render color emoji
    (4-byte Unicode / Supplementary Multilingual Plane characters).
    They appear as empty squares or are completely skipped.

    The correct solution:
    1. Use Pillow (PIL) with the OS emoji font (Segoe UI Emoji on Windows /
       Noto Color Emoji on Linux) to draw text + emoji as a RGBA PNG.
    2. Then use FFmpeg's `overlay` filter to composite the PNG on the video.

    This gives us real, full-color 🔥👉❤️ emoji in the output video.

    Args:
        text:        The string to render (may contain emoji).
        out_png:     Output path for the transparent overlay PNG.
        canvas_w/h:  Match the video dimensions (default 1080×1920).
        font_size:   Text font size in pixels.
        text_color:  RGBA tuple for the text.
        box_color:   RGBA tuple for the background pill box.
        box_padding: Padding around the text inside the box.
        y_pos:       Y coordinate of the box top. None = vertically centred.

    Returns:
        out_png path (same as input).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ImportError(
            "Pillow is required for emoji rendering. Run: pip install Pillow"
        )

    # ── Choose font with emoji support ──────────────────────────────────────
    EMOJI_FONTS_WIN = [
        r"C:\Windows\Fonts\seguiemj.ttf",   # Segoe UI Emoji (Windows 10/11)
        r"C:\Windows\Fonts\seguisym.ttf",   # Segoe UI Symbol (fallback)
    ]
    EMOJI_FONTS_LINUX = [
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    ]
    EMOJI_FONTS_MAC = [
        "/System/Library/Fonts/Apple Color Emoji.ttc",
    ]

    font_path = None
    for candidate in EMOJI_FONTS_WIN + EMOJI_FONTS_LINUX + EMOJI_FONTS_MAC:
        if os.path.exists(candidate):
            font_path = candidate
            break

    try:
        if font_path:
            font = ImageFont.truetype(font_path, font_size)
        else:
            log.warning("No emoji font found; using Pillow default (no emoji).")
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # ── Measure text size ────────────────────────────────────────────────────
    dummy = Image.new("RGBA", (1, 1))
    draw  = ImageDraw.Draw(dummy)
    bbox  = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    box_w = text_w + box_padding * 2
    box_h = text_h + box_padding * 2

    # Centre box horizontally; default y = vertically centred
    box_x = (canvas_w - box_w) // 2
    box_y = y_pos if y_pos is not None else (canvas_h - box_h) // 2

    # ── Draw onto transparent canvas ─────────────────────────────────────────
    img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background pill (rounded rectangle)
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=box_h // 3,
        fill=box_color,
    )

    # Text centred inside the box
    text_x = box_x + box_padding
    text_y = box_y + box_padding
    draw.text((text_x, text_y), text, font=font, fill=text_color, embedded_color=True)

    img.save(out_png, "PNG")
    log.info("Emoji overlay saved → %s (%dx%d box)", out_png, box_w, box_h)
    return out_png


def _pick_local_meme_image() -> str | None:
    """
    Pick a random local meme/sticker image from settings.memes_dir.
    Supported: .png, .webp, .jpg, .jpeg
    """
    if not getattr(settings, "enable_memes", False):
        return None
    memes_dir = getattr(settings, "memes_dir", "") or ""
    if not memes_dir or not os.path.exists(memes_dir):
        return None

    exts = {".png", ".webp", ".jpg", ".jpeg"}
    candidates: list[str] = []
    try:
        for fn in os.listdir(memes_dir):
            p = os.path.join(memes_dir, fn)
            if not os.path.isfile(p):
                continue
            _, ext = os.path.splitext(fn)
            if ext.lower() in exts:
                candidates.append(p)
    except Exception:
        return None

    if not candidates:
        return None
    return random.choice(candidates)


class FFmpegService:
    """Wraps FFmpeg operations needed by the pipeline."""

    def crop_to_vertical(
        self,
        input_path: str,
        duration_sec: int | None = None,
        start_sec: int | None = None,
    ) -> str:
        """
        Convert a horizontal video to vertical (9:16) by center-cropping,
        and trim it to `duration_sec` seconds.

        Args:
            input_path:   Absolute path to the source video file.
            duration_sec: Length of the output clip (seconds). Uses config default if None.
            start_sec:    Start offset in the source video. Uses config default if None.

        Returns:
            Absolute path of the output file (<base>_short.mp4).

        Raises:
            FileNotFoundError: If input_path does not exist.
            RuntimeError: If FFmpeg fails.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input video not found: {input_path}")

        duration_sec = duration_sec if duration_sec is not None else settings.default_clip_duration
        start_sec    = start_sec    if start_sec    is not None else settings.default_start_sec

        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_short.mp4"

        # The "Blurred Background" & "Anti-Copyright" effect:
        # 1. Background (bg): Speed up 7%, scale up, center-crop, and blur heavily.
        # 2. Foreground (fg): Speed up 7%, adjust contrast/brightness to beat pixel hashing, scale down to fit.
        # 3. Audio (outa): Speed up 7% to match visual frames perfectly.
        w  = settings.crop_target_width
        h  = settings.crop_target_height
        
        # 1.07x Speedup alters both Video Hash and Audio Signature without destroying viewer retention!
        filter_complex = (
            f"[0:v]setpts=PTS/1.07,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:20[bg];"
            f"[0:v]setpts=PTS/1.07,scale={w}:{h}:force_original_aspect_ratio=decrease,eq=contrast=1.05:brightness=0.03[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[outv];"
            f"[0:a]atempo=1.07[outa]"
        )

        _run([
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-i", input_path,
            "-t", str(duration_sec),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", settings.ffmpeg_preset,
            "-crf", str(settings.ffmpeg_crf),
            "-c:a", "aac",
            "-b:a", settings.audio_bitrate,
            "-movflags", "+faststart",
            output_path,
        ])

        log.info("Crop complete: %s", output_path)
        return output_path

    def burn_captions(
        self,
        video_path: str,
        srt_path: str,
        heading_text: str | None = None,
        style_hint: str | None = None,
        category_hint: str | None = None,
    ) -> tuple[str, bool]:
        """
        Apply a RANDOM visual style to the video. Picks one of 4 styles each run:
          Style 0 – Classic: blurred bg + English captions + heading banner
          Style 1 – Fullscreen: full-screen clip, large title only (no captions)
          Style 2 – Emoji Pop: fullscreen + emoji-rich caption strip at bottom
          Style 3 – Minimal: fullscreen clip, small pill heading, NO captions

        Args:
            video_path:   Absolute path to the video.
            srt_path:     Absolute path to the SRT file (English captions).
            heading_text: Title / heading string.

        Returns:
            Tuple of (final_video_path, captioned: bool).
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        base, _ = os.path.splitext(video_path)
        final_path = f"{base}_final.mp4"

        heading_text = heading_text if heading_text is not None else settings.default_heading_text
        clean_heading = _safe_text(heading_text)[:55]   # strip only drawtext-unsafe chars

        # Emoji-decorated style configs — full color emoji via Pillow overlay
        # NOTE: We intentionally avoid CENTERED titles because they block main content.
        STYLES = [
            # 0 – Classic: yellow captions + top heading banner with emoji
            {"heading": f"🔥 {clean_heading} 🔥",  "follow": "👉 Follow for more!",
             "h_color": (255, 255, 255, 255), "h_box": (0, 0, 0, 190),  "h_size": 58, "h_y": 120,
             "f_color": (255, 255, 255, 255), "f_box": (0, 0, 0, 160),  "f_size": 42, "f_y": 1780,
             "scale": False, "captions": True},
            # 1 – Fullscreen: large title near top, no captions
            {"heading": f"✨ {clean_heading} ✨", "follow": None,
             "h_color": (255, 255, 255, 255), "h_box": (0, 0, 0, 160),  "h_size": 70, "h_y": 140,
             "f_color": None,                  "f_box": None,            "f_size": 0,  "f_y": None,
             "scale": True,  "captions": False},
            # 2 – Bold Pop: gold title + orange follow strip
            {"heading": f"🔥 {clean_heading}",    "follow": "👉 Follow for more!  👈",
             "h_color": (255, 215, 0,   255), "h_box": (0, 0, 0, 200),  "h_size": 56, "h_y": 80,
             "f_color": (255, 255, 255, 255), "f_box": (230, 57, 0, 210),"f_size": 44, "f_y": 1780,
             "scale": True,  "captions": True},
            # 3 – Minimal: soft white title + subtle follow watermark
            {"heading": clean_heading,            "follow": "❤️  Follow for more",
             "h_color": (255, 255, 255, 240), "h_box": (26, 26, 26, 230), "h_size": 50, "h_y": 90,
             "f_color": (200, 200, 200, 200), "f_box": (0, 0, 0, 100),    "f_size": 38, "f_y": 1830,
             "scale": True,  "captions": False},
        ]

        def _pick_style() -> int:
            hint = (style_hint or category_hint or "").lower()
            if any(k in hint for k in ["geopolit", "war", "defense", "current affairs", "news"]):
                return 3  # minimal
            if any(k in hint for k in ["comedy", "meme", "entertainment"]):
                return 2  # bold pop + captions
            if any(k in hint for k in ["cooking", "food", "travel", "lifestyle"]):
                return 1  # fullscreen title
            if any(k in hint for k in ["scam", "safety", "finance", "earning"]):
                return 0  # classic + captions
            return random.randint(0, 3)

        style = _pick_style()
        s        = STYLES[style]
        log.info("Applying emoji-overlay style #%d for: %s", style, video_path)

        srt_exists  = os.path.exists(srt_path)
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:") if srt_exists else ""
        w = settings.crop_target_width
        h = settings.crop_target_height

        # ── Render emoji overlays as transparent PNGs via Pillow ─────────────
        tmp_pngs = []

        heading_png  = f"{base}_overlay_heading.png"
        _render_emoji_overlay(
            text=s["heading"], out_png=heading_png,
            canvas_w=w, canvas_h=h,
            font_size=s["h_size"],
            text_color=s["h_color"], box_color=s["h_box"],
            box_padding=24,
            y_pos=s["h_y"],
        )
        tmp_pngs.append(heading_png)

        follow_png = None
        if s["follow"]:
            follow_png = f"{base}_overlay_follow.png"
            _render_emoji_overlay(
                text=s["follow"], out_png=follow_png,
                canvas_w=w, canvas_h=h,
                font_size=s["f_size"],
                text_color=s["f_color"], box_color=s["f_box"],
                box_padding=20,
                y_pos=s["f_y"],
            )
            tmp_pngs.append(follow_png)

        # ── Build FFmpeg filter_complex ───────────────────────────────────────
        # Input 0: video  |  Input 1: heading PNG  |  Input 2: follow PNG (optional) | (optional) meme sticker
        scale_vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            if s["scale"] else ""
        )

        filter_parts = []
        if scale_vf:
            filter_parts.append(f"[0:v]{scale_vf}[scaled]")
            prev = "scaled"
        else:
            prev = "0:v"

        # Optional intro variation effects (adds variety and reduces “same format” feel)
        intro_blur = float(getattr(settings, "intro_blur_sec", 0.0) or 0.0)
        intro_zoom = bool(getattr(settings, "intro_zoom", False))
        if intro_blur > 0:
            filter_parts.append(f"[{prev}]boxblur=8:8:enable='between(t,0,{intro_blur})'[vblur]")
            prev = "vblur"
        if intro_zoom:
            # Subtle zoom-in over time; safe and lightweight.
            filter_parts.append(f"[{prev}]scale=iw*1.03:ih*1.03,crop=iw:ih[vzoom]")
            prev = "vzoom"

        # Overlay heading PNG
        filter_parts.append(f"[{prev}][1:v]overlay=0:0[v1]")
        prev = "v1"
        overlay_inputs = [heading_png]

        # Overlay follow PNG
        if follow_png:
            filter_parts.append(f"[{prev}][2:v]overlay=0:0[v2]")
            prev = "v2"
            overlay_inputs.append(follow_png)

        # Optional meme/sticker overlay (local pack)
        meme_path = _pick_local_meme_image()
        meme_input_idx = None
        if meme_path:
            meme_input_idx = 1 + len(overlay_inputs)  # because cmd adds overlay_inputs after video
            # Scale meme sticker and overlay for a short window (adds humor/attention)
            mw = int(getattr(settings, "meme_overlay_width_px", 420))
            margin = int(getattr(settings, "meme_overlay_margin_px", 36))
            start_t = float(getattr(settings, "meme_overlay_start_sec", 2.0))
            end_t = float(getattr(settings, "meme_overlay_end_sec", 5.5))

            filter_parts.append(f"[{meme_input_idx}:v]scale={mw}:-1[meme]")
            # Random corner placement (top-right or bottom-left)
            if random.random() < 0.5:
                x_expr = f"W-w-{margin}"
                y_expr = f"{margin}"
            else:
                x_expr = f"{margin}"
                y_expr = f"H-h-{margin}"

            filter_parts.append(
                f"[{prev}][meme]overlay={x_expr}:{y_expr}:enable='between(t,{start_t},{end_t})'[vmeme]"
            )
            prev = "vmeme"
            overlay_inputs.append(meme_path)

        # Burn SRT captions on top (styles that support it)
        final_label = prev
        if s["captions"] and srt_exists:
            cap_style = (
                "FontSize=13,PrimaryColour=&H0000FFFF,"
                "Bold=1,Outline=2,Shadow=1,Alignment=2,MarginV=200"
            )
            filter_parts.append(
                f"[{prev}]subtitles='{srt_escaped}':force_style='{cap_style}'[vfinal]"
            )
            final_label = "vfinal"

        filter_complex = ";".join(filter_parts)

        # Build command
        cmd = [get_ffmpeg_binary(), "-y", "-i", video_path]
        for asset in overlay_inputs:
            # If meme is an image, loop it as a video stream so overlay works for time window
            _, ext = os.path.splitext(asset)
            if ext.lower() in {".png", ".webp", ".jpg", ".jpeg"} and asset == meme_path:
                cmd += ["-loop", "1", "-i", asset]
            else:
                cmd += ["-i", asset]

        cmd += [
            "-filter_complex", filter_complex,
            "-map", f"[{final_label}]",
            "-map", "0:a",
            "-c:v", "libx264",
            "-preset", settings.ffmpeg_preset,
            "-crf", str(settings.ffmpeg_crf),
            "-c:a", "aac",
            "-b:a", settings.audio_bitrate,
            final_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.error("FFmpeg style render failed:\\n%s", result.stderr)
            raise RuntimeError(f"FFmpeg error: {result.stderr[-800:]}")

        # Cleanup temp PNG overlays
        for png in tmp_pngs:
            try:
                os.remove(png)
            except Exception:
                pass

        captioned = s["captions"] and srt_exists
        log.info("Style #%d emoji-overlay applied. Output: %s", style, final_path)
        return final_path, captioned

        log.info("Style #%d applied. Output: %s", style, final_path)
        return final_path, captioned

    def combine_generative_video(self, video_clips: list[str], audio_path: str, bg_music_path: str | None = None) -> str:
        """
        Step 7: Video Editing (Editor)
        Combines downloaded stock clips and voiceover into a final short.
        Optionally mixes in a soft background music track at low volume.
        """
        if not video_clips:
            raise ValueError("No video clips provided for combination.")

        w = settings.crop_target_width
        h = settings.crop_target_height
        out_path = os.path.join(settings.tmp_dir, "generative_merged.mp4")

        # Build filter_complex for scaling and center-cropping each clip
        filter_complex = ""
        for i in range(len(video_clips)):
            filter_complex += (
                f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},setsar=1,fps=30[v{i}];"
            )

        concat_inputs = "".join([f"[v{i}]" for i in range(len(video_clips))])
        filter_complex += f"{concat_inputs}concat=n={len(video_clips)}:v=1:a=0[outv]"

        voice_idx  = len(video_clips)   # voice audio input index
        music_idx  = voice_idx + 1      # bg music input index (if used)
        use_music  = bg_music_path and os.path.exists(bg_music_path)

        cmd = ["ffmpeg", "-y"]
        for clip in video_clips:
            cmd.extend(["-stream_loop", "-1", "-i", clip])
        cmd.extend(["-i", audio_path])   # voice

        if use_music:
            cmd.extend(["-stream_loop", "-1", "-i", bg_music_path])  # bg music
            # Mix voice (full volume) with music (15% volume)
            music_vol = float(getattr(settings, "bg_music_volume", 0.10))
            music_tempo = float(getattr(settings, "bg_music_tempo", 0.92))
            music_lowpass = int(getattr(settings, "bg_music_lowpass_hz", 9000))
            audio_filter = (
                f"[{voice_idx}:a]volume=1.0[voice];"
                f"[{music_idx}:a]"
                f"atempo={music_tempo},lowpass=f={music_lowpass},volume={music_vol}[music];"
                "[voice][music]amix=inputs=2:duration=first:dropout_transition=2[outa]"
            )
            filter_complex += ";" + audio_filter
            audio_map = "[outa]"
            log.info("Mixing background music from: %s", bg_music_path)
        else:
            audio_map = f"{voice_idx}:a"

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", audio_map,
            "-c:v", "libx264",
            "-preset", settings.ffmpeg_preset,
            "-crf", str(settings.ffmpeg_crf),
            "-c:a", "aac",
            "-b:a", settings.audio_bitrate,
            "-shortest",
            "-movflags", "+faststart",
            out_path
        ])

        _run(cmd)
        log.info("Generative Video Merged: %s", out_path)
        return out_path

