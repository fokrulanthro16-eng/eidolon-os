# EIDOLON OS — Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Next.js Frontend                        │
│                    http://localhost:3000                      │
│  Timeline │ Sessions │ Videos │ Graph │ Profile │ Chat       │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/JSON
┌────────────────────────▼────────────────────────────────────┐
│                    FastAPI Backend                           │
│                  http://127.0.0.1:8010                       │
│                                                             │
│  /memory   /vision   /voice   /pdf   /graph                 │
│  /sessions /suggestions /profile /video /export /health     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Storage Layer (JSON files)                 │
│                                                             │
│  storage/memory-db/memories.json    ← all memories          │
│  storage/session-db/sessions.json   ← session cache         │
│  storage/session-db/dismissed_suggestions.json              │
│  storage/video-db/video_index.json  ← video metadata        │
│  storage/video-db/events/*.json     ← per-video events      │
│  storage/screenshots/               ← PNG screenshots        │
│  storage/uploads/pdfs/              ← PDF files             │
│  storage/uploads/audio/             ← audio files           │
│  storage/videos/                    ← video files           │
│  storage/videos/thumbnails/         ← event thumbnails      │
└─────────────────────────────────────────────────────────────┘
```

## Route Map

| Prefix | File | Purpose |
|---|---|---|
| /health | routes/health.py | Liveness + readiness |
| /system | routes/system.py | System info, screen watcher control |
| /memory | routes/memory.py | Ingest image/PDF/audio, search, timeline |
| /vision | routes/vision.py | Ingest video → MemoryItem |
| /voice | routes/voice.py | Ingest audio → voice MemoryItem |
| /pdf | routes/pdf.py | PDF Chat, list, summary, related |
| /chat | routes/chat.py | Streaming LLM chat (Ollama/rule-based) |
| /sessions | routes/sessions.py | Session list, detail, replay |
| /export | routes/export.py | JSON export of memories + sessions |
| /summary | routes/summary.py | Daily summary generation |
| /graph | routes/graph.py | Memory relationship graph |
| /profile | routes/profile.py | Digital soul profile |
| /suggestions | routes/suggestions.py | Grounded suggestions + dismiss |
| /video | routes/video.py | Video CRUD + event queries |

## Backend Services

### Core
- `memory_store.py` — thread-safe atomic JSON (RLock + .tmp.json → .replace())
- `embedding_service.py` — sentence-transformers, LRU cache, lazy load
- `search_service.py` — hybrid: 0.35 keyword + 0.55 semantic + 0.10 recency
- `session_service.py` — session detection from memory timestamps

### Ingestion
- `ocr_service.py` — Tesseract OCR (graceful fallback)
- `pdf_service.py` — PyMuPDF extraction + OCR scanned pages
- `pdf_chunk_service.py` — 800–1200 char overlapping chunks, MD5 dedup
- `pdf_chat_service.py` — rule-based Q&A from chunk retrieval
- `vision_service.py` — heuristic scene analysis (PIL + regex)
- `voice_service.py` — faster-whisper transcription (optional)
- `video_service.py` — YOLO nano + IoU tracker + motion detector
- `video_store.py` — atomic video metadata + event files

### Intelligence
- `memory_graph_service.py` — 6 edge types, dedup, ego-graphs
- `profile_service.py` — cached behavioural profile, privacy-first
- `suggestion_service.py` — 5 suggestion types, stable IDs, dismiss persistence

### Workers
- `screen_watcher.py` — screenshot → OCR → vision → memory (background)

## Data Flow: Memory Ingestion

```
Upload / Screenshot
      │
      ▼
 Validate + Save file
      │
      ▼
 Extract text  (OCR → PyMuPDF → Whisper → YOLO depending on type)
      │
      ▼
 Build MemoryItem  { id, type, title, text, metadata, tags }
      │
      ▼
 embed_for_storage()  →  optional 384-dim embedding
      │
      ▼
 memory_store.add()  →  atomic write to memories.json
      │
      ▼
 Return 201 to client
```

## Data Flow: Video Intelligence

```
POST /vision/ingest-video
      │
      ├── 1. Save video file  (VIDEOS_DIR / {video_id}_{filename})
      ├── 2. video_store.add_video()  →  video_index.json
      ├── 3. memory_store.add()       →  MemoryItem type=video (placeholder)
      │
      └── 4. Background thread:
                ├── OpenCV VideoCapture  (sample at 1 fps)
                ├── YOLO nano  →  detect CCTV classes per frame
                ├── _SimpleTracker  →  IoU-based cross-frame tracking
                ├── _MotionDetector →  cv2.absdiff() > 1.5% threshold
                ├── Emit events  (person_appeared / crowd / motion / vehicle / bag)
                ├── Save JPEG thumbnails  →  VIDEO_THUMBS_DIR
                ├── video_store.append_events()  (batches of 50)
                └── memory_store.update()        (full analysis results)
```

## Memory Graph

| Edge Type | Detection |
|---|---|
| same_session | Memories share session_id |
| near_time | Created within 30 minutes |
| same_app | metadata.app_name matches |
| same_topic | 3+ shared keywords (4+ chars, noise-filtered) |
| workflow_related | metadata.workflow_type matches (non-trivial) |
| semantic_match | Cosine similarity ≥ 0.70 (requires embeddings) |

## Search Scoring

```
score = 0.35 × keyword_score
      + 0.55 × semantic_score  (0 if embeddings unavailable)
      + 0.10 × recency_score
```

Where `recency_score = 1 / (1 + age_days × 0.1)`.
