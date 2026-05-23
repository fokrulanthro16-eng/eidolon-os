# EIDOLON OS — System Flow

Data flows through the system in clearly separated pipelines, all local, none cloud.

---

## Memory Ingestion Pipelines

### Screen Capture Pipeline
```
screen_watcher (cron, 30s)
  → PIL.ImageGrab.grab()
  → ocr_service.extract_text()          # pytesseract or fallback
  → vision_intelligence_service         # app fingerprint, workflow type, smart title
    → analyze_screenshot_enhanced()
  → memory_store.add()                  # type=screenshot
  → embedding_service.embed_for_storage()
  → session_service (auto-clustering)
```

### PDF Ingestion Pipeline
```
POST /memory/ingest-pdf
  → pdf_service.extract_text()          # pymupdf or fallback
  → pdf_service.chunk_text()
  → memory_store.add()                  # type=pdf
  → embedding_service.embed_for_storage()
```

### Voice Ingestion Pipeline
```
POST /memory/ingest-audio
  → voice_service.transcribe()          # faster-whisper base model
  → memory_store.add()                  # type=voice
  → embedding_service.embed_for_storage()
```

### Video Upload Pipeline
```
POST /vision/ingest-video
  → video_service._analyze_video_worker() (background thread)
    → cv2.VideoCapture()
    → YOLO("yolov8n.pt").track()        # object detection + tracking
    → prediction_service.PredictionTracker.update()
    → per-event: memory_store.add()     # type=video
    → thumbnail saved to storage/videos/thumbnails/
```

### Live Camera Pipeline (single camera)
```
POST /vision/camera/start
  → camera_service._camera_worker() (daemon thread)
    → cv2.VideoCapture(0)
    → YOLO tracking at ~1 fps
    → prediction_service.camera_tracker.update()
    → motion detected + cooldown elapsed:
      → _store_camera_event()           # type=video, source=live_camera
      → _save_thumb()                   # storage/screenshots/camera-events/
```

### Multi-Camera Pipeline (Phase 16)
```
POST /cameras/add
  → multi_camera_service.add_camera()  # registry entry
  → _save_registry()                   # storage/cameras/camera_registry.json

POST /cameras/{id}/start
  → multi_camera_service._camera_worker(camera_id) (daemon thread)
    → same pipeline as single camera above
    → isolated Lock + Event + state dict per camera
```

---

## Search Pipeline

### Keyword Search
```
POST /memory/search { query }
  → search_service.search_memories(query, items)
    → keyword matching on title+text+tags
    → recency scoring
  → returns ranked results
```

### Semantic Search (if sentence-transformers installed)
```
POST /memory/search { query }
  → embedding_service.embed_query(query)
  → cosine similarity against stored embeddings
  → hybrid score = 0.4*keyword + 0.6*semantic
```

### Neural Cross-Modal Search (Phase 15)
```
POST /search/neural { query, filters, limit }
  → cross_modal_search_service.neural_search()
    → optional date/type filtering
    → search_service.search_memories() as base
    → _modality_weight() boost (1.25x if query hints match type)
    → _build_grouped() → grouped_by_modality
    → _build_timeline() → chronological ordering
    → _answer_summary() → rule-based natural language summary
```

---

## Replay Pipeline (Phase 13)

```
GET /replay/day?date=YYYY-MM-DD
  → replay_intelligence_service.replay_day()
    → filter memories by date
    → sort chronologically
    → _find_key_moments() → detect debug, AI research, uploads, app switches
    → _build_result() → standardised replay schema

GET /replay/topic?query=...
  → search_memories(query) for relevance ranking
  → then sort chronologically
  → same key moment detection

GET /replay/modality?type=...
  → filter by type, sort chronologically
```

---

## Digital Soul Pipeline (Phase 14)

```
GET /soul/patterns
  → digital_soul_service._compute_patterns(memories)
    → 7-day / 30-day windows
    → count coding/debugging/research/pdf/voice memories
    → detect Multi-Tool Workflow (app diversity)
    → 90s TTL cache

GET /soul/workflow-rhythm
  → _compute_workflow_rhythm(memories)
    → hourly heatmap (0-23)
    → day-of-week breakdown
    → dominant scene per peak hour

GET /soul/project-memory
  → _compute_project_memory(memories)
    → window title parsing for project names
    → session_store.get_sessions() for unfinished work
    → keyword extraction (NOISE_WORDS filtered)
```

---

## World Model Pipeline (Phase 17)

```
GET /world/state
  → world_model_service.get_world_state(memories, predictions)
    → 5s TTL cache check
    → get_recent_camera_events(memories, limit=30)  # type=video, live/upload
    → _extract_entity_tracks(events)                # {label: count, last_seen}
    → camera_tracker.get_active()                   # prediction service
    → _build_risk_notes(entities, predictions)      # max 5, [Estimated] prefix
    → _zone(cx, cy) for each prediction → zone grid (3×3)
    → world_state description text + confidence
    → disclaimer: "[Estimated] heuristic, not guaranteed"
```

---

## Brain Chat Pipeline (Phase 18)

```
POST /brain/chat { message, history }
  → get_active_brain()              # singleton: local_semantic | ollama | lmstudio
  → search_memories(message)[:8]   # top 8 relevant memories
  → build_memory_context(...)       # inject matched memories into context
  → brain.generate_with_history(message, context, history)
    → if llm_active: call LLM (Ollama/LMStudio) with prompt
    → if llm unavailable: synthesize_answer() (rule-based fallback)
  → returns { answer, brain_mode, llm_active, fallback_used, sources_count }

Brain providers:
  local_semantic → chat_memory_service.synthesize_answer() (no LLM)
  ollama         → POST http://localhost:11434/api/chat
  lmstudio       → POST http://127.0.0.1:1234/v1/chat/completions (OpenAI compat)
```

---

## Agent Pipeline (Phase 12)

```
POST /agent/execute { action, args }
  → agent_service.execute_action(action, args)
    → dispatch to lambda via _ACTIONS dict
    → _SAFE_APPS allowlist for open_app
    → shell=True ONLY for browser/URL actions
    → os.startfile() for folders/files
    → returns { success, message, ... }
```

---

## Storage Layout

```
storage/
  memory-db/
    memories.json          # all memories (append-only, JSON array)
  session-db/
    sessions.json          # detected sessions
  screenshots/
    *.png                  # captured screen frames
    camera-events/         # single-camera thumbnails
    camera-{id}/           # multi-camera thumbnails
  uploads/
    pdfs/                  # uploaded PDF files
    audio/                 # uploaded audio files
  videos/
    *.mp4                  # uploaded video files
    thumbnails/            # video frame thumbnails
  cameras/
    camera_registry.json   # multi-camera persistence
```
