# 🎬 YouTube Short Generator API

A **fully local REST API pipeline** that replaces Apify, SSH-based FFmpeg, and SSH-based Whisper with clean, scalable HTTP endpoints — designed for seamless integration with **n8n HTTP Request nodes**.

---

## 📁 Project Structure

```
YoutubeVideoDownloader/
├── main.py           # FastAPI application (all endpoints)
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

---

## ⚙️ Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.10+ | Runtime | https://python.org |
| FFmpeg | Video processing | https://ffmpeg.org/download.html |
| Whisper (`openai-whisper`) | Transcription | Installed via pip |

> **FFmpeg must be on your system PATH.**
> Verify with: `ffmpeg -version`

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
py -m pip install -r requirements.txt
```

### 2. Start the server
```bash
py -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Open the interactive docs
```
http://localhost:8000/docs
```

### 4. (Optional) Expose publicly for n8n Cloud via ngrok
```bash
ngrok http 8000
# Use the https://xxxx.ngrok.io URL in your n8n HTTP Request nodes
```

---

## 📡 API Reference

### Overview

| # | Method | Endpoint | Replaces | Description |
|---|--------|----------|---------|-------------|
| – | GET | `/` | – | Health check |
| 1 | POST | `/download` | Apify downloader | Download YouTube video |
| 2 | POST | `/process/crop` | SSH FFmpeg | Crop to 9:16 vertical |
| 3 | POST | `/transcribe` | SSH Whisper | Generate SRT subtitles |
| 4 | POST | `/process/captions` | SSH FFmpeg | Burn subtitles into video |
| 5 | POST | `/cleanup` | – | Delete temp files |
| 6 | POST | `/generate-short` | All of the above | Full pipeline in one call |

---

### 1️⃣ `POST /download`
Download a YouTube video using yt-dlp.

**Request:**
```json
{
  "videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```
**Response:**
```json
{
  "status": "success",
  "videoId": "dQw4w9WgXcQ",
  "filePath": "C:\\Users\\...\\AppData\\Local\\Temp\\dQw4w9WgXcQ.mp4",
  "cached": false
}
```
**Curl:**
```bash
curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -d '{"videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

---

### 2️⃣ `POST /process/crop`
Convert horizontal video to vertical 9:16 with optional trim.

**Request:**
```json
{
  "inputPath": "C:\\Temp\\dQw4w9WgXcQ.mp4",
  "durationSec": 60,
  "startSec": 0
}
```
**Response:**
```json
{
  "status": "success",
  "outputPath": "C:\\Temp\\dQw4w9WgXcQ_short.mp4"
}
```
**Curl:**
```bash
curl -X POST http://localhost:8000/process/crop \
  -H "Content-Type: application/json" \
  -d '{"inputPath": "C:/Temp/dQw4w9WgXcQ.mp4", "durationSec": 60, "startSec": 0}'
```

---

### 3️⃣ `POST /transcribe`
Generate SRT subtitles using Whisper (runs fully locally).

**Request:**
```json
{
  "videoPath": "C:\\Temp\\dQw4w9WgXcQ_short.mp4",
  "model": "base"
}
```
**Available models:** `tiny` | `base` | `small` | `medium` | `large`  
*(Larger = more accurate but slower)*

**Response:**
```json
{
  "status": "success",
  "srtPath": "C:\\Temp\\dQw4w9WgXcQ_short.srt"
}
```
**Curl:**
```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{"videoPath": "C:/Temp/dQw4w9WgXcQ_short.mp4", "model": "base"}'
```

---

### 4️⃣ `POST /process/captions`
Burn SRT subtitles into the video using FFmpeg.

**Request:**
```json
{
  "videoPath": "C:\\Temp\\dQw4w9WgXcQ_short.mp4",
  "srtPath":   "C:\\Temp\\dQw4w9WgXcQ_short.srt"
}
```
**Response:**
```json
{
  "status": "success",
  "finalPath": "C:\\Temp\\dQw4w9WgXcQ_short_final.mp4",
  "captioned": true
}
```
> If SRT is missing, returns original video with `"captioned": false`.

**Curl:**
```bash
curl -X POST http://localhost:8000/process/captions \
  -H "Content-Type: application/json" \
  -d '{"videoPath": "C:/Temp/dQw4w9WgXcQ_short.mp4", "srtPath": "C:/Temp/dQw4w9WgXcQ_short.srt"}'
```

---

### 5️⃣ `POST /cleanup`
Delete all temp files for a given video ID.

**Request:**
```json
{
  "videoId": "dQw4w9WgXcQ"
}
```
**Response:**
```json
{
  "status": "success",
  "videoId": "dQw4w9WgXcQ",
  "deleted": ["C:\\Temp\\dQw4w9WgXcQ.mp4", "..."],
  "failed": []
}
```

---

### 6️⃣ `POST /generate-short` ⭐ (Recommended for n8n)
Runs the **entire pipeline** in a single HTTP call.

**Request:**
```json
{
  "videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "durationSec": 60,
  "startSec": 0,
  "whisperModel": "base"
}
```
**Response:**
```json
{
  "status": "success",
  "videoId": "dQw4w9WgXcQ",
  "finalVideoPath": "C:\\Temp\\dQw4w9WgXcQ_short_final.mp4",
  "steps": [
    { "step": "download",      "result": { ... } },
    { "step": "crop",          "result": { ... } },
    { "step": "transcribe",    "result": { ... } },
    { "step": "burn_captions", "result": { ... } }
  ]
}
```

**Curl:**
```bash
curl -X POST http://localhost:8000/generate-short \
  -H "Content-Type: application/json" \
  -d '{"videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "durationSec": 60}'
```

---

## 🔗 n8n Integration

Replace your existing n8n nodes as follows:

| Old Node | New n8n Node | Endpoint |
|----------|-------------|----------|
| Apify YouTube Downloader | HTTP Request (POST) | `/download` |
| SSH → FFmpeg crop | HTTP Request (POST) | `/process/crop` |
| SSH → Whisper | HTTP Request (POST) | `/transcribe` |
| SSH → FFmpeg subtitles | HTTP Request (POST) | `/process/captions` |
| All of the above | HTTP Request (POST) | `/generate-short` |

**n8n HTTP Request node config example:**
- **Method:** POST
- **URL:** `http://localhost:8000/generate-short`  
  *(or your ngrok URL for n8n Cloud)*
- **Body Content Type:** JSON
- **Body:** `{ "videoUrl": "{{ $json.videoUrl }}" }`

---

## 🔄 Pipeline Flow

```
YouTube URL
    │
    ▼
POST /download          ← yt-dlp → /tmp/VIDEO_ID.mp4
    │
    ▼
POST /process/crop      ← FFmpeg → /tmp/VIDEO_ID_short.mp4  (9:16, 60s)
    │
    ▼
POST /transcribe        ← Whisper → /tmp/VIDEO_ID_short.srt
    │
    ▼
POST /process/captions  ← FFmpeg → /tmp/VIDEO_ID_short_final.mp4
    │
    ▼
Upload to YouTube (handled by n8n)
    │
    ▼
POST /cleanup           ← Delete all /tmp/VIDEO_ID* files
```

---

## 🐛 Error Handling

All endpoints return standard HTTP error codes:

| Code | Meaning |
|------|---------|
| 400 | Bad request (invalid URL, bad path) |
| 404 | File not found |
| 500 | FFmpeg / Whisper / internal error |

Error response shape:
```json
{
  "detail": "Human-readable error message"
}
```

Transcription errors in `/generate-short` are **non-fatal** — the pipeline continues without subtitles and returns `"captioned": false`.
