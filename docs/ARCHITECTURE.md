# EIDOLON OS — Architecture

**Phase 22 — Identity Engine**  
Local-first. Gemini-powered (opt-in). No cloud lock-in.

---

## High-Level Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           EIDOLON OS  v0.22.0                                │
│                                                                              │
│   ┌──────────────────────────┐  HTTP/JSON  ┌───────────────────────────────┐ │
│   │  Next.js 16  (port 3000) │◄───────────►│  FastAPI backend (port 8010)  │ │
│   │  React 19 · TypeScript 5 │             │                               │ │
│   │                          │             │  Routes (23 modules)          │ │
│   │  Tabs:                   │             │  Services (36+ modules)       │ │
│   │   Timeline   Sessions    │             │  Workers (daemon threads)     │ │
│   │   Vision     Replay      │             │                               │ │
│   │   Soul       Graph       │             └──────────────┬────────────────┘ │
│   │   Profile    Trends      │                            │                  │
│   │   Agent      Brain Chat  │                            ▼                  │
│   └──────────────────────────┘             ┌───────────────────────────────┐ │
│                                            │        Local Storage          │ │
│   Cognitive Core Orb (header)              │        storage/               │ │
│   ● Green  = Gemini live                   │        ├─ memory-db/          │ │
│   ● Yellow = Local fallback                │        ├─ session-db/         │ │
│   ● Red    = Backend unreachable           │        ├─ screenshots/        │ │
│                                            │        ├─ uploads/            │ │
│                                            │        ├─ videos/             │ │
│                                            │        ├─ cameras/            │ │
│                                            │        └─ identity-db/        │ │
│                                            └───────────────────────────────┘ │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  Gemini Hybrid Layer  (opt-in — BRAIN_PROVIDER=gemini)               │   │
│   │                                                                      │   │
│   │  GeminiBridgeService                                                 │   │
│   │  ├─ generate_with_history()   chat answers + agentic tool loop       │   │
│   │  ├─ generate_stream()         SSE word-by-word streaming             │   │
│   │  ├─ generate_from_prompt()    profile / timeline / identity synth    │   │
│   │  └─ _local_fallback()         always-safe rule-based synthesis       │   │
│   │                                                                      │   │
│   │  google-genai SDK 1.74.0  ↕  aistudio.google.com (opt-in only)      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  Identity Engine  (Phase 22)                                         │   │
│   │                                                                      │   │
│   │  identity_service.py                                                 │   │
│   │  ├─ _detect_projects()    keyword-pattern matching → project list    │   │
│   │  ├─ _infer_focus()        48-hour recency scoring → current focus    │   │
│   │  ├─ _infer_goals()        trigger-keyword matching → goal list       │   │
│   │  ├─ _suggest_next()       active project → next task suggestion      │   │
│   │  ├─ get_or_build()        30-min TTL cache in identity-db/           │   │
│   │  └─ local_identity_summary()  rule-based fallback paragraph          │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  Optional Local LLM Brains                                           │   │
│   │  Ollama (port 11434)  ·  LM Studio (port 1234)                       │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  Background Workers (daemon threads)                                 │   │
│   │  screen_watcher · camera_worker(s) · video_analyzer · embed_backfill │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│        No mandatory internet. No database server. No auth service.           │
│        Gemini is opt-in. Local semantic fallback always active.              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Backend — apps/api/

### Route Layer (apps/api/app/api/routes/)

| Router | Prefix | Phase | Description |
|--------|--------|-------|-------------|
| health.py | /health | 1 | Liveness check |
| memory.py | /memory | 1 | CRUD for memory items |
| sessions.py | /sessions | 5 | Session clustering |
| export.py | /export | 6 | Export to JSON/CSV |
| summary.py | /summary | 6 | Daily summary |
| pdf.py | /pdf | 7 | PDF ingestion + chat |
| profile.py | /profile | 7 | Behavioral profile |
| suggestions.py | /suggestions | 8 | Auto-suggestions (no LLM) |
| voice.py | /voice | 9 | Audio transcription |
| video.py | /video | 10 | YOLO video analysis |
| vision.py | /vision | 10 | Camera + event stream |
| camera.py | /vision/camera | 10 | Single live camera |
| graph.py | /graph | 9+ | Memory relationship graph |
| chat.py | /chat | 4 | Ask Eidolon (stream + query) |
| agent.py | /agent | 12 | Local action registry |
| replay_v2.py | /replay | 13 | Smart session replay |
| digital_soul.py | /soul | 14 | Behavioral patterns |
| neural_search.py | /search | 15 | Cross-modal neural search |
| cameras.py | /cameras | 16 | Multi-camera registry |
| world_model.py | /world | 17 | Heuristic scene state |
| brain.py | /brain | 18 | Brain status + chat + reset |
| intelligence.py | /intelligence | 21 | Profile, timeline, clusters, insights |
| identity.py | /identity | 22 | Identity profile, projects, next |

### Service Layer (apps/api/app/services/)

**Memory & Search**
- `memory_store.py` — JSON-backed store, O(n) reads, append-write
- `search_service.py` — hybrid keyword + semantic (BM25 + cosine) search
- `embedding_service.py` — sentence-transformers with graceful fallback
- `session_service.py` — temporal gap-based clustering into sessions
- `chat_memory_service.py` — temporal filter extraction, term isolation
- `chat_session.py` — in-memory conversation history (last 8 turns)
- `cross_modal_search_service.py` — Phase 15 neural search with modality boosting

**Vision & Media**
- `ocr_service.py` — pytesseract with fallback
- `vision_service.py` — basic scene classification
- `vision_intelligence_service.py` — 600+ app fingerprints, workflow type, smart titles
- `workflow_service.py` — workflow period aggregation
- `video_service.py` — YOLO analysis pipeline + _SimpleTracker
- `camera_service.py` — single live camera worker
- `multi_camera_service.py` — named multi-camera registry (Phase 16)
- `prediction_service.py` — linear velocity trajectory extrapolation
- `voice_service.py` — faster-whisper transcription

**Intelligence (Phase 21)**
- `intelligence_service.py` — memory clustering, 14-day trends, domain scores, Gemini profile + timeline synthesis
- `gemini_bridge_service.py` — Gemini SDK wrapper; generate_with_history, generate_stream, generate_from_prompt, _local_fallback
- `gemini_tool_registry.py` — agentic tool declarations (search_memories, get_daily_summary, get_user_profile, list_sessions)
- `gemini_vision_agent.py` — vision-specific Gemini agent path

**Identity (Phase 22)**
- `identity_service.py` — project detection, focus inference, goal inference, next suggestion, 30-min TTL cache in `storage/identity-db/`

**Brain Routing**
- `llm/brain_router.py` — singleton factory: local_semantic | ollama | lmstudio | gemini
- `llm/local_brain.py` — rule-based + optional Ollama integration
- `llm/ollama_brain.py` — Ollama adapter
- `llm/lmstudio_brain.py` — LM Studio adapter (urllib only)
- `llm/base.py` — BaseBrain abstract class + BrainMode enum
- `llm/memory_context.py` — memory context injection and compression

**Profile & Behavioral**
- `profile_service.py` — base behavioral profile from metadata
- `digital_soul_service.py` — workflow rhythm, project memory, behavioral patterns
- `suggestions_service.py` — grounded autonomous suggestions (no LLM required)
- `agent_service.py` — safe local action registry (_SAFE_APPS allowlist)
- `graph_service.py` — memory relationship graph (same_session, near_time, same_app, same_topic)
- `replay_service.py` — session replay (Phase 6)
- `replay_intelligence_service.py` — smart replay with key moment detection (Phase 13)
- `world_model_service.py` — heuristic scene aggregation, 5s TTL cache
- `pdf_service.py` — PDF chunking + semantic Q&A

**Storage**
- `storage_service.py` — directory initialisation on startup
- `session_store.py` — session persistence

### Worker Layer
- `app/workers/screen_watcher.py` — periodic screenshot daemon (30s interval)

---

## Frontend — apps/web/

Single-file React app: `apps/web/src/app/page.tsx`

### Tab Structure

| Tab | Key Features |
|-----|-------------|
| **Timeline** | Memory cards, search, upload (PDF/audio/video/image), temporal filter |
| **Sessions** | Session cards with gap-based clustering, per-session replay |
| **Vision/CCTV** | Video upload + YOLO analysis, live webcam, multi-camera registry, World Model |
| **Replay** | Replay Studio 2.0 — by date / topic / modality, key moment detection |
| **Soul** | Hourly heatmap, workflow rhythm, project memory, behavioral patterns |
| **Graph** | Memory relationship edges (SVG-free, canvas-free) |
| **Profile** | Identity Snapshot (Phase 22) · Identity Card · Cognitive Profile (Phase 21) · Behavioral Profile |
| **Trends** | 14-day activity chart, domain trend arrows, memory cluster bars, Gemini narrative |
| **Agent** | Local action registry, workflow timeline, Brain Chat |

### State Management
- React `useState` / `useCallback` / `useEffect` / `useRef`
- No Redux, no Zustand — all local component state
- Polling via `setInterval` refs for camera/video status and brain orb (30s)

---

## Gemini Integration

### Call Sites

| Service | Method | Purpose | Max tokens |
|---------|--------|---------|-----------|
| `gemini_bridge_service` | `generate_with_history()` | Brain Chat (/brain/chat) | 512 |
| `gemini_bridge_service` | `generate_stream()` | Ask Eidolon SSE stream | 600 |
| `intelligence_service` | `generate_from_prompt()` | Cognitive profile paragraph | 350 |
| `intelligence_service` | `generate_from_prompt()` | Timeline narrative | 200 |
| `identity.py` (route) | `generate_from_prompt()` | Identity paragraph | 280 |
| `identity.py` (route) | `generate_from_prompt()` | Next task suggestion | 100 |

### Fallback Chain

```
User query
    │
    ▼
GeminiBridgeService.generate_with_history()
    │
    ├── Gemini active? ──YES──► Gemini 2.0 Flash API call
    │                               │
    │                               ├── Success ──► streamed answer
    │                               │
    │                               └── Quota / Auth / Error
    │                                       │
    └── No ◄─────────────────────────────────┘
            │
            ▼
        _local_fallback()
            │
            ├── identity context available?
            │       YES ──► local_identity_summary() → synthesised paragraph
            │
            └── memory titles + sources ──► domain-pattern inference paragraph
```

No call path returns a blank response or an uncaught exception.

### Reasoning Mode Detection

Questions containing any of these phrases trigger reasoning mode:

- Identity: `"who am i"`, `"what am i building"`, `"active projects"`, `"work on next"`
- Pattern: `"what patterns"`, `"summarize"`, `"recent activity"`, `"my profile"`
- Profile: `"tell me about me"`, `"describe me"`, `"my habits"`, `"my work"`

In reasoning mode:
1. Most-recent memories are loaded regardless of keyword match
2. Identity Engine context is injected (`active_projects`, `current_focus`, `inferred_goals`)
3. `_SYSTEM_REASONING` prompt replaces `_SYSTEM_DEFAULT`
4. Identity context is labelled with `Primary project:` so Gemini anchors on EIDOLON OS

---

## Identity Engine (Phase 22)

### Project Detection

```
For each memory:
  For each PROJECT_PATTERN (EIDOLON OS, Gemini Hybrid Layer, Camera & Vision, ...):
    Score = keyword hits × recency weight
    Status = active (<7 days) | recent (<30 days) | dormant

Sort by: status priority DESC, confidence DESC
EIDOLON OS always leads (sorted to index 0 in response paths)
```

### Focus Inference

```
Cutoff = now - 48 hours  (fallback: now - 7 days)
Score project patterns against recent memories only
Return top-scoring project as current_focus
```

### Cache

Identity context is stored in `storage/identity-db/identity.json` with a 30-minute TTL. The cache is invalidated when memory count changes. `user_summary` is populated by Gemini when `/identity/profile` is called; all other fields are computed locally.

---

## Data Model — MemoryItem

```typescript
{
  id:         string     // "mem_20260531_143200_abc123"
  type:       string     // screenshot | pdf | voice | video | image | text
  title:      string
  text:       string     // OCR text, transcript, description
  file_path:  string | null
  source:     string     // screen_watcher | pdf_upload | live_camera | ...
  tags:       string[]
  metadata: {
    app_name?:        string
    window_title?:    string
    scene_type?:      string   // coding | browsing | debugging | ...
    workflow_type?:   string   // coding | research | api_testing | ...
    probable_task?:   string
    smart_title?:     string
    active_tools?:    string[]
    confidence?:      number
    event_type?:      string   // camera/video events
    labels?:          string[]
    thumbnail_url?:   string
    camera_id?:       string
    prediction_type?: string
    direction?:       string
    speed?:           number
  }
  created_at: string     // ISO 8601 UTC
  updated_at: string
  embedding?: number[]   // sentence-transformer vector (optional)
}
```

---

## Concurrency Model

| Worker | Mechanism | Notes |
|--------|-----------|-------|
| Screen watcher | Standalone process | `python -m app.workers.screen_watcher` |
| Single camera | `threading.Thread(daemon=True)` | `camera_service` |
| Multi-camera | One thread per camera | `multi_camera_service._CAMERAS` |
| Video analysis | One thread per video | `video_service._active_workers` |
| Embedding backfill | Daemon thread on startup | `threading.Thread(target=_backfill, daemon=True)` |
| Brain streaming | Daemon thread per request | `threading.Thread(name="brain-stream", daemon=True)` |

All workers use `threading.Event` for graceful stop and `threading.Lock` for state isolation.

---

## Security & Privacy

- **No outbound network calls** except optional Gemini API (opt-in) and Ollama (localhost)
- **No authentication** — single-user local deployment by design
- **No telemetry, analytics, or crash reporting**
- **Static file mounts** serve only from `storage/` — no path traversal possible
- **Agent actions**: `_SAFE_APPS` allowlist; `shell=True` only for `start <URL>` commands
- **Camera**: user must explicitly start each camera; no auto-start on boot
- **Gemini receives** only memory text snippets (not raw screenshots or files)
- **`GEMINI_ALLOW_SYSTEM_LOCKDOWN=true`** prevents any memory context from being sent to Gemini
- **API key** never logged, printed, or included in any HTTP response

---

## Local-First Guarantee

Every feature in EIDOLON OS has a working offline path:

| Feature | Online (Gemini) | Offline (local) |
|---------|-----------------|-----------------|
| Chat answers | Gemini synthesis | Rule-based + memory titles |
| Identity reasoning | Gemini paragraph | `local_identity_summary()` |
| Cognitive profile | Gemini paragraph | Rule-based domain summary |
| Timeline narrative | Gemini paragraph | Counts + trend arrows |
| Object detection | — | YOLO nano (local) |
| Voice transcription | — | faster-whisper (local) |
| OCR | — | Tesseract (local) |
| Semantic search | — | sentence-transformers (local) |

Setting `BRAIN_PROVIDER=local_semantic` (the default) makes zero API calls. All AI runs on-device.
