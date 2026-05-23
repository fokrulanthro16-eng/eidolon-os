# EIDOLON OS — Feature Map

## Core Features (always active, zero extra deps)

### Screen Intelligence
- Periodic screen capture (30s interval, configurable)
- Active window detection (app name, window title, exe)
- Heuristic scene analysis (editor / browser / terminal / chat)
- Workflow detection from app combination patterns

### Memory System
- Atomic JSON persistence (thread-safe, crash-resistant)
- Timeline view (newest first)
- Hybrid search (keyword + recency)
- Memory CRUD (create, read, delete)
- Tag system (source, app, type, detected classes)

### Session Intelligence
- Automatic session detection from memory timestamps
- Session title generation from top keywords
- Session summary + stats
- Temporal session browser

### Replay Engine
- Frame-by-frame session replay
- Keyboard navigation (← → Space Escape)
- Auto-advance playback
- Screenshot display per frame

### PDF Brain
- PDF upload + PyMuPDF text extraction
- OCR fallback for scanned pages (requires Tesseract)
- Chunk-based Q&A (800–1200 char overlapping chunks, MD5 dedup)
- Multi-PDF search mode
- PDF summary endpoint (abstract + keywords)
- Related PDFs by embedding similarity

### Export
- JSON export of all memories
- JSON export of all sessions
- Daily summary generation

---

## Optional Features (activate with pip install)

### Voice Memory (requires faster-whisper)
- Audio upload: .mp3 .wav .m4a .ogg .flac .webm
- Local Whisper transcription (base model, CPU int8)
- Language detection
- Transcript stored as searchable memory (type=voice)
- Fallback: stores audio + placeholder memory if Whisper absent

### Video / CCTV Intelligence (requires opencv-python-headless)
- Video upload: .mp4 .avi .mov .mkv .wmv .webm .m4v
- Motion detection via frame differencing (1.5% threshold)
- Fallback to motion-only if ultralytics absent

### YOLO Object Detection (requires ultralytics, in addition to opencv)
- YOLO nano model (~6 MB auto-download)
- CCTV-class detection: person, vehicle, bicycle, motorcycle, bus, truck, bags
- IoU-based cross-frame tracking
- Event types: person_appeared, crowd_detected, vehicle_appeared, bag_detected, motion_detected
- JPEG thumbnail generation for key events
- Video memories are searchable: "show videos with people", "car detected"

### Semantic Search (requires sentence-transformers)
- all-MiniLM-L6-v2 (384-dim, ~90 MB, auto-download)
- Works fully offline after first download
- Upgrades search from keyword-only to hybrid
- PDF chunk retrieval uses cosine similarity
- Memory graph adds semantic_match edges

---

## Intelligence Features (built-in, no extra deps)

### Memory Graph
- 6 edge types: same_session, near_time, same_app, same_topic, workflow_related, semantic_match
- Ego-graph for individual memories
- Session-level subgraphs
- Overview graph (latest 120 memories)

### Digital Soul Profile
- App usage heatmap + percentages
- Hourly activity distribution + peak period
- Scene type distribution
- Workflow pattern detection
- Recurring topic keywords
- Productivity notes
- Privacy-first: metadata only, no content analysis

### Autonomous Suggestions (up to 5, memory-backed)
- pdf_cluster: 3+ PDFs share a keyword
- app_dominance: one app > 40% of captures
- time_pattern: activity concentrated in peak hours
- topic_insight: keyword recurring in recent memories
- session_pattern: deep-work session detected
- Persistent dismiss via JSON file
- Stable IDs (content-based hash, not random)

---

## API Summary

```
GET  /health                   liveness check
GET  /system/info              system status
POST /memory/ingest-image      image → OCR → memory
POST /memory/ingest-pdf        PDF → extract → memory
POST /memory/ingest-audio      audio → transcribe → memory
POST /memory/search            hybrid search
GET  /memory/timeline          all memories, newest first
DELETE /memory/{id}            delete memory

POST /vision/ingest-video      video → YOLO → memory (searchable)
POST /voice/ingest-audio       audio → Whisper → voice memory

GET  /video/list               video records
GET  /video/{id}/events        event timeline
GET  /video/{id}/status        analysis progress
GET  /video/search?q=          keyword search across events

POST /pdf/chat                 ask question about PDFs
GET  /pdf/list                 PDF memory list
GET  /pdf/{id}/summary         abstract + keywords
GET  /pdf/related/{id}         related PDFs

GET  /sessions/list            session list
GET  /sessions/{id}            session detail + memories
GET  /sessions/{id}/replay     replay frames

GET  /graph/overview           memory relationship graph
GET  /graph/memory/{id}        ego-graph
GET  /graph/session/{id}       session graph

GET  /profile/summary          digital soul profile

GET  /suggestions              up to 5 grounded suggestions
GET  /suggestions/list         alias
POST /suggestions/{id}/dismiss dismiss persistently

GET  /export/memories          JSON download
GET  /export/sessions          JSON download
GET  /summary/daily            daily activity summary

GET  /docs                     Swagger UI
```
