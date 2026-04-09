# 📌 Project Overview

* Project name: **YouTube Shorts Factory (YoutubeVideoDownloader)**
* What problem it solves: Automates end-to-end Shorts production (idea/script, visuals, voice, editing, captions, metadata, upload/distribution) so creators do not need to manually stitch multiple tools.
* Target users: Solo creators, social media teams, faceless content channels, automation builders (n8n/CLI users).
* Key features (high-level):
  * AI-assisted script generation (two-stage strategy + script)
  * Visual generation via Google Veo (with Pexels fallback)
  * Voiceover generation (Sarvam) + subtitle generation (Whisper)
  * Automated FFmpeg editing for 9:16 Shorts, style variations, overlays, meme stickers, and background music
  * One-run publishing workflow to YouTube + Telegram

---

# 🛠 Tech Stack

## Backend

* Language: **Python 3.10+**
* Framework: **FastAPI** (API endpoints) + **CLI workflow runner**
* Key Libraries:
  * `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`
  * `yt-dlp`
  * `openai-whisper`
  * `google-genai` (Veo/Flow integration)
  * `sarvamai`
  * `requests`, `inquirer`, `rich`

## Database

* Primary DB: **None (file-based state storage)**
* Secondary DB (if any): **None**

## Cloud & DevOps

* Cloud Provider: **Optional / hybrid** (local-first app, external APIs for AI)
* Services Used (SQS, EC2, S3, etc.):
  * Google GenAI API (Veo generation)
  * OpenRouter API (Mistral models for strategy/script/metadata)
  * YouTube Data API + YouTube Upload API
  * Telegram Bot API
  * Pexels API

## Other Tools

* Messaging: **Telegram Bot API**
* Caching: **File-level cache + dedupe files in `videos/`**
* API Docs: **FastAPI Swagger at `/docs`**
* Build Tool: **Pip + requirements.txt**

---

# 🏗 Architecture

* Type (Monolith / Microservices): **Modular Monolith**
* High-level explanation:
  * A single Python project with clear service boundaries (`download`, `workflow`, `ffmpeg`, `whisper`, `veo`, `youtube_upload`).
  * Exposed through both API routes and an interactive CLI orchestrator.
* Communication between services:
  * In-process service calls from CLI/API routers.
  * External communication through HTTP APIs (OpenRouter, Google GenAI, YouTube, Telegram, Pexels).
* Design patterns used:
  * Service Layer pattern
  * Router/Controller abstraction (FastAPI routers)
  * Config/Settings injection via `BaseSettings`
  * Fallback strategy (Veo -> Pexels)
  * Pipeline orchestration pattern

---

# 📂 Folder Structure (Explain Clearly)

Explain each layer:

* controller: FastAPI routers in `app/routers/` handling request/response boundaries.
* service: Business logic and external API integrations in `app/services/`.
* repository: **Not a formal DB repository layer**; file-based persistence handled inside services (e.g., category/processed IDs files).
* dto: Request/response schemas in `app/schemas/`.
* entity: **Not used as ORM entities** (no relational DB); domain objects are dict-based payloads.
* config: App configuration in `app/config.py`.
* util: Shared helpers in `app/utils/` (logger, ffmpeg resolver, file helpers).

Also include a sample folder tree.

```text
YoutubeVideoDownloader/
├── app/
│   ├── app.py
│   ├── config.py
│   ├── routers/
│   │   ├── download.py
│   │   ├── process.py
│   │   ├── transcribe.py
│   │   ├── workflow.py
│   │   └── orchestrator.py
│   ├── schemas/
│   │   ├── download.py
│   │   ├── process.py
│   │   ├── transcribe.py
│   │   └── workflow.py
│   ├── services/
│   │   ├── downloader.py
│   │   ├── workflow.py
│   │   ├── ffmpeg.py
│   │   ├── whisper.py
│   │   ├── veo_service.py
│   │   └── youtube_upload.py
│   └── utils/
│       ├── logger.py
│       ├── file_utils.py
│       └── ffmpeg_resolver.py
├── assets/
│   └── memes/
├── videos/
├── cli.py
├── auth.py
├── main.py
├── requirements.txt
└── README.md
```

---

# 🧩 Key Modules

List and explain:

* Auth Module
* User Module
* Appointment Module
* (Add based on project)

For each module:

* Responsibility
* Main APIs
* Dependencies

### Auth Module (YouTube OAuth)
* Responsibility: Handles OAuth consent flow and token caching for YouTube uploads.
* Main APIs:
  * `auth.py` flow
  * `YouTubeUploadService._authenticate()`
* Dependencies: Google OAuth libs, `client_secret_*.json`, token cache file.

### User Module
* Responsibility: **N/A (no end-user account system in current scope).**
* Main APIs: None.
* Dependencies: None.

### Appointment Module
* Responsibility: **N/A (domain equivalent is content job orchestration).**
* Main APIs: CLI pipeline trigger + orchestrator routes.
* Dependencies: Workflow, FFmpeg, Whisper, Veo, YouTube, Telegram services.

### Content Strategy & Script Module
* Responsibility: Two-stage AI generation (idea brief -> final script JSON), quality gate, retries.
* Main APIs:
  * `WorkflowService.generate_idea_brief_v3()`
  * `WorkflowService.generate_script_from_brief_v3()`
  * `WorkflowService.generate_short_v3()`
* Dependencies: OpenRouter (Mistral models), category profile map, quality checks.

### Visual Generation Module
* Responsibility: Generate scene clips via Google Veo or fallback to Pexels.
* Main APIs:
  * `VeoService.generate_clips_for_scenes()`
  * `WorkflowService.fetch_visuals()`
* Dependencies: `google-genai`, Pexels API, prompt builder.

### Media Processing Module
* Responsibility: Assemble clips, voice, captions, overlays, meme stickers, style effects.
* Main APIs:
  * `FFmpegService.combine_generative_video()`
  * `FFmpegService.burn_captions()`
  * `FFmpegService.crop_to_vertical()`
* Dependencies: FFmpeg binary, local filesystem assets.

### Distribution Module
* Responsibility: Publish generated Shorts and notifications.
* Main APIs:
  * `YouTubeUploadService.upload_short()`
  * `WorkflowService.send_telegram_alert()`
  * `WorkflowService.send_telegram_video()`
* Dependencies: YouTube API, Telegram Bot API.

---

# 🔄 Important Flows

## 1. Authentication Flow

Step-by-step:

* Login
  * User runs `auth.py` or chooses a YouTube upload path.
* Token generation
  * OAuth browser flow generates access + refresh token.
  * Token saved in `youtube_token.json`.
* Validation
  * On each upload run, token is loaded and refreshed if expired.

## 2. Booking / Appointment Flow

Step-by-step from user action to DB

> Domain mapping: “Booking/Appointment” in this project = **Short generation job execution**.

1. User starts job from CLI (`step_generative_pipeline`) or API.
2. Category + subtopic selected (rotation + dedupe state files).
3. Stage 1 AI generates locked idea brief.
4. Stage 2 AI writes script JSON + scene hints + query list.
5. Voice generated from script.
6. Visual clips generated (Veo preferred, Pexels fallback).
7. FFmpeg merges visuals + audio + subtitles + overlays.
8. Metadata assembled and distribution starts.
9. Output persisted to local `videos/` and uploaded/sent.
10. State files updated (`last_category.txt`, used IDs, processed list).

## 3. Publish & Notification Flow

1. Final media rendered and validated.
2. YouTube upload executes if enabled.
3. Telegram alert sent with short URL/local path.
4. Telegram video sent as media file.
5. Cleanup runs for temporary artifacts based on user selection.

---

# 🔐 Security

* Authentication type (JWT, OAuth, etc.):
  * OAuth2 for YouTube upload access.
  * API keys for OpenRouter, Google GenAI, Pexels, Telegram.
* Role handling:
  * No multi-role internal auth currently (single operator model).
* Data protection:
  * Secrets stored via `.env` / settings.
  * Avoid hardcoding credentials in source.
  * Token cache and generated media remain local by default.

---

# ⚡ Performance & Scalability

* Caching:
  * Local video cache and dedupe files reduce repeated downloads/generation.
* Async processing:
  * Veo generation uses polling; pipeline is synchronous today but can be queued.
* Load handling:
  * Current design is single-worker local pipeline.
  * Horizontal scale path: queue-based job runners + object storage + stateless API workers.

---

# 🚨 Important Notes for Developers

* Coding conventions:
  * Keep business logic in `services`, validation in `schemas`, transport in `routers`.
  * Preserve strict JSON contracts for AI-generated outputs.
* Common pitfalls:
  * Malformed AI JSON responses -> always pass through parser/repair.
  * Long scripts -> enforce word cap before TTS/render.
  * FFmpeg path issues on Windows -> use resolver utility.
  * Veo quotas/timeouts -> ensure Pexels fallback remains enabled.
* Key business rules:
  * Shorts must be vertical-first (`9:16`).
  * Prefer Mistral models for cost control.
  * Maintain uniqueness across runs (topics, Pexels IDs, processed source videos).
  * Do not mark content as processed before successful output generation.
