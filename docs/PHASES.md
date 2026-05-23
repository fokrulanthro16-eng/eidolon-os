# EIDOLON OS — Phase-by-Phase Build Log

Each phase corresponds to a discrete feature batch. Phases build on top of each other
without breaking existing functionality. All phases are local-first.

---

## Phase 1 — Core Memory Store
- JSON memory store at `storage/memory-db/memories.json`
- CRUD: ingest image (OCR), list, delete, export
- Session detection from timestamps
- Basic keyword search

## Phase 2 — Screen Capture + OCR
- Screenshot ingestion via `POST /memory/ingest-image`
- Tesseract OCR with pytesseract (optional — graceful fallback)
- Active window title detection (Windows/macOS/Linux)
- Memory type: `screenshot`

## Phase 3 — Session Management
- Auto-detect sessions from 30-minute idle gaps
- `GET /sessions/list`, `GET /sessions/{id}/replay`
- Session-level export

## Phase 4 — Semantic Search
- Hybrid keyword + semantic search
- sentence-transformers (optional) — falls back to keyword if not installed
- Embedding backfill on startup (background thread)
- `POST /memory/search` with score + confidence

## Phase 5 — PDF Brain
- PDF upload + text extraction (PyMuPDF)
- Chunk storage with page references
- PDF chat: `POST /pdf/chat` — retrieval + rule-based Q&A
- Memory type: `pdf`

## Phase 6 — Daily Summary + Export
- `GET /agent/daily-summary` — active hours, top apps, workflow breakdown
- Export: JSON / Markdown / CSV via `POST /export`
- Summary tab in frontend

## Phase 7 — Digital Profile
- `GET /profile/summary` — behavioral profile from memory metadata
- Top apps, top keywords, type distribution, productivity notes
- 90s TTL cache

## Phase 8 — Auto-Suggestions
- `GET /suggestions` — grounded autonomous suggestions
- Based on recent activity, unfinished sessions, idle time
- No hallucination: all suggestions reference actual memories

## Phase 9 — Voice Memory
- Audio upload + faster-whisper transcription (optional, CPU)
- `POST /memory/ingest-audio`
- Memory type: `voice`
- Voice search via existing hybrid search

## Phase 10 — Video Intelligence
- Video upload + OpenCV frame sampling + YOLO nano object detection
- `POST /vision/ingest-video`, `GET /video/{id}/events`
- Live camera: `POST /vision/camera/start`
- Motion + object events → memory store
- Memory type: `video`

## Phase 11 — Vision Intelligence
- App fingerprinting from window titles (600+ patterns)
- Workflow type detection (coding, research, design, communication, etc.)
- Probable task inference
- Active tool detection
- Embedded in screenshot ingestion path

## Phase 12 — AI Agent Mode
- Safe local action registry (allowlist-only)
- `GET /agent/actions`, `POST /agent/execute`
- Safe actions: open_app, open_folder, summarize_today, search_memories, start/stop screen watch
- No shell injection, no arbitrary code execution

## Phase 13 — Replay Engine 2.0
- Replay by: date, topic, modality, session
- Key moment detection (debug_start, ai_research, pdf_upload, etc.)
- `GET /replay/day`, `/replay/topic`, `/replay/modality`, `/replay/session/{id}/smart`

## Phase 14 — Digital Soul Intelligence
- Behavioral patterns from memory metadata
- Workflow rhythm: peak hours, day-of-week heatmap
- Project memory: recurring topics, unfinished sessions
- `GET /soul/profile`, `/soul/patterns`, `/soul/workflow-rhythm`, `/soul/project-memory`

## Phase 15 — Neural Cross-Modal Search
- Cross-modal retrieval across screenshot/voice/pdf/video
- Modality weight boost (1.25×)
- Rule-based answer_summary
- `POST /search/neural`

## Phase 16 — Multi-Camera Intelligence
- Named camera registry (webcam index, RTSP URL, file)
- Isolated worker per camera (thread + lock + event)
- Persisted to `storage/cameras/camera_registry.json`
- `GET /cameras/list`, `POST /cameras/add`, `POST /cameras/{id}/start`, etc.

## Phase 17 — World Model Layer
- Heuristic scene-state aggregation from camera events
- Active entities, movement predictions ([Estimated]), zones (3×3 grid)
- Risk notes with explicit uncertainty labels
- 5s TTL cache
- `GET /world/state`, `/world/predictions`, `/world/events`

## Phase 18 — Brain Adapter (Optional Local LLM)
- Default: `local_semantic` (zero dependencies, always works)
- Optional: `BRAIN_PROVIDER=ollama` or `BRAIN_PROVIDER=lmstudio`
- No model download, no crash, graceful fallback
- `GET /brain/status`, `POST /brain/chat`, `POST /brain/reset`

## Phase 19 — Desktop Foundation
- Planning documents in `desktop/` (Tauri plan, Electron plan)
- Scripts: `start_all.ps1`, `stop_all.ps1`, `start_desktop_dev.ps1`
- "Desktop Ready" badge in frontend profile tab
- No desktop shell installed — documentation only

## Phase 20 — Demo Launch Polish
- Complete documentation suite (ROADMAP, PHASES, PRIVACY, SETUP_WINDOWS, TROUBLESHOOTING)
- `.env.example` with all configurable variables
- `.gitignore` protecting storage, models, secrets, build artifacts
- README overhaul with feature showcase and setup guide
- TypeScript verified clean, all backends integrated
