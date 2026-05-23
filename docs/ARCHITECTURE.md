# EIDOLON OS — Architecture

**Phase 20 — Demo Launch Ready**

Local-first, modular, no cloud dependency.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│                    EIDOLON OS                           │
│                                                         │
│  ┌─────────────┐         ┌─────────────────────────┐   │
│  │  Next.js 14 │ ←HTTP→  │   FastAPI (port 8010)   │   │
│  │  (port 3000)│         │                         │   │
│  └─────────────┘         │  Routes → Services      │   │
│                           │  Services → Storage     │   │
│                           └─────────────────────────┘   │
│                                      ↓                  │
│                           ┌─────────────────────────┐   │
│                           │   Local Storage          │   │
│                           │   storage/               │   │
│                           │   ├── memory-db/         │   │
│                           │   ├── session-db/        │   │
│                           │   ├── screenshots/       │   │
│                           │   ├── uploads/           │   │
│                           │   ├── videos/            │   │
│                           │   └── cameras/           │   │
│                           └─────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Backend — apps/api/

### Route Layer (apps/api/app/api/routes/)

| Router | Prefix | Phase |
|--------|--------|-------|
| health.py | /health | 1 |
| memory.py | /memory | 1 |
| sessions.py | /sessions | 5 |
| export.py | /export | 6 |
| summary.py | /summary | 6 |
| pdf.py | /pdf | 7 |
| profile.py | /profile | 7 |
| suggestions.py | /suggestions | 9 |
| voice.py | /voice | 8 |
| video.py | /video | 10 |
| vision.py | /vision | 10 |
| camera.py | /vision/camera | 10 |
| graph.py | /graph | 9 |
| chat.py | /chat | 4 |
| agent.py | /agent | 12 |
| replay_v2.py | /replay | 13 |
| digital_soul.py | /soul | 14 |
| neural_search.py | /search | 15 |
| cameras.py | /cameras | 16 |
| world_model.py | /world | 17 |
| brain.py | /brain | 18 |

### Service Layer (apps/api/app/services/)

**Memory & Search**
- `memory_store.py` — JSON-backed store, O(n) reads, append-write
- `search_service.py` — hybrid keyword + semantic search
- `embedding_service.py` — sentence-transformers with graceful fallback
- `session_service.py` — temporal clustering of memories into sessions
- `cross_modal_search_service.py` — Phase 15 neural search with modality boosting

**Vision & Media**
- `ocr_service.py` — pytesseract with fallback
- `vision_service.py` — basic scene classification
- `vision_intelligence_service.py` — Phase 11: app fingerprinting + workflow detection
- `workflow_service.py` — Phase 11: workflow period aggregation
- `video_service.py` — YOLO analysis pipeline + _SimpleTracker
- `camera_service.py` — single live camera worker (Phase 10)
- `multi_camera_service.py` — named multi-camera registry (Phase 16)
- `prediction_service.py` — trajectory prediction via linear velocity extrapolation
- `voice_service.py` — faster-whisper transcription

**Intelligence**
- `profile_service.py` — base behavioral profile from metadata
- `digital_soul_service.py` — Phase 14: patterns, workflow rhythm, project memory
- `replay_service.py` — Phase 6 session replay
- `replay_intelligence_service.py` — Phase 13: smart replay with key moments
- `suggestions_service.py` — grounded autonomous suggestions (no LLM required)
- `agent_service.py` — Phase 12: safe local action registry
- `graph_service.py` — memory relationship graph

**Storage**
- `storage_service.py` — directory initialization
- `session_store.py` — session persistence
- `pdf_service.py` — PDF chunking + chat

**Brain**
- `llm/local_brain.py` — rule-based + optional Ollama integration
- `llm/brain_router.py` — Phase 18: singleton factory (local_semantic | ollama | lmstudio)
- `llm/ollama_brain.py` — Phase 18: Ollama adapter (subclass of LocalBrain)
- `llm/lmstudio_brain.py` — Phase 18: LM Studio adapter (urllib only, no openai package)
- `llm/base.py` — BaseBrain abstract base + BrainMode enum
- `llm/prompt_builder.py` — system prompt + user prompt templates
- `llm/memory_context.py` — memory context injection helper

**World Model**
- `world_model_service.py` — Phase 17: heuristic scene aggregation (5s TTL cache)

### Worker Layer (apps/api/app/workers/)
- `screen_watcher.py` — periodic screen capture daemon

---

## Frontend — apps/web/

Single-file React app: `apps/web/src/app/page.tsx` (~5000 lines)

### Tab Structure

| Tab | Content |
|-----|---------|
| Timeline | Memory cards with search, upload actions |
| Sessions | Session cards with replay |
| Vision/CCTV | Video upload, live camera, multi-camera, predictions, world model |
| Replay | Replay Studio 2.0 (day/topic/modality) |
| Soul | Digital Soul: patterns, workflow rhythm, project memory |
| Graph | Memory relationship graph (canvas-free, SVG-free) |
| Profile | Behavioral profile + Desktop Ready badge |
| Agent | AI Agent Console with actions, workflow timeline, Brain Chat |

### State Management
- React `useState` / `useCallback` / `useEffect` / `useRef`
- No Redux, no Zustand — all local component state
- Polling via `setInterval` refs for camera + video status

### Key Components
- `ReplayPlayer` — fullscreen session replay player (keyboard nav, scrubber)
- `SessionCard`, `VideoCard`, `EventCard` — display cards
- `ChatPanel`, `SuggestionsPanel` — overlay panels
- `AppBadge`, `TypeBadge` — inline metadata chips

---

## Data Model — MemoryItem

```typescript
{
  id:         string     // e.g. "mem_20240523_143200_abc123"
  type:       string     // screenshot | pdf | voice | video | image | text
  title:      string
  text:       string     // OCR text, transcript, description
  file_path:  string | null
  source:     string     // screen_watcher | pdf_upload | live_camera | ...
  tags:       string[]
  metadata: {
    app_name?:       string
    window_title?:   string
    scene_type?:     string   // coding | browsing | debugging | ...
    workflow_type?:  string   // coding | research | api_testing | ...
    probable_task?:  string   // natural language description
    smart_title?:    string   // enhanced title
    active_tools?:   string[]
    confidence?:     number
    // video/camera-specific:
    event_type?:     string
    labels?:         string[]
    thumbnail_url?:  string
    camera_id?:      string
    // prediction:
    prediction_type?: string
    direction?:       string
    speed?:           number
  }
  created_at: string    // ISO 8601 UTC
  updated_at: string
  embedding?: number[]  // sentence-transformer vector (optional)
}
```

---

## Concurrency Model

- **Single-camera worker**: `threading.Thread(daemon=True)` via `camera_service`
- **Multi-camera workers**: one `threading.Thread` per camera in `multi_camera_service._CAMERAS`
- **Video analysis**: one background thread per video via `video_service._active_workers`
- **Screen watcher**: runs as a standalone process (`python -m app.workers.screen_watcher`)
- **Embedding backfill**: daemon thread on startup (`threading.Thread(target=_backfill, daemon=True)`)

All workers use `threading.Event` for graceful stop, `threading.Lock` for state isolation.

---

## Security & Privacy

- No outbound network calls (except optional Ollama on localhost)
- No authentication — designed for single-user local deployment
- No telemetry, no analytics, no crash reporting
- Static file mounts serve only from `storage/` (no path traversal possible via FastAPI)
- Agent actions: `_SAFE_APPS` allowlist; shell=True only for `start <URL>` commands
- Camera: user must explicitly start each camera; no auto-start on boot
