# EIDOLON OS — Demo Script

A step-by-step walkthrough of every major feature. Intended for live demos.

---

## Setup (before demo)

```bash
# Terminal 1 — API
cd apps/api
.venv\Scripts\activate
uvicorn main:app --host 127.0.0.1 --port 8010 --reload

# Terminal 2 — Frontend
cd apps/web
npm run dev

# Terminal 3 (optional) — Screen watcher
cd apps/api
python -m app.workers.screen_watcher
```

Open http://localhost:3000

---

## 1. Timeline — The Memory Stream

**What to show:**
- The Timeline tab shows all memories captured so far, newest first
- Cards show type badge, app name, timestamp, OCR text preview
- Phase 11 badges: `probable_task` in italic cyan, workflow type chip, active tools

**Say:** "Every screenshot, PDF, voice memo, and video event ends up here. Fully searchable."

---

## 2. Search

**Demo:**
- Type "coding" or "FastAPI" in the search bar → hit Enter
- Show hybrid search results with scores

**Say:** "Keyword search always works. If sentence-transformers is installed, it upgrades to hybrid semantic + keyword."

---

## 3. PDF Brain

**Demo:**
- Click Upload PDF → select any PDF
- Wait for ingestion confirmation
- Click "◫ Ask PDF" button → ask "What is this document about?"
- Show chunked retrieval answer with source pages

---

## 4. Voice Memory

**Demo:**
- Click Upload Audio → select any .mp3/.wav/.m4a
- Show transcription stored as voice memory in Timeline
- Search for a word from the transcript

---

## 5. Video Intelligence

**Demo:**
- Go to Vision/CCTV tab
- Click Upload Video → select any security camera footage or video
- Show analysis progress (YOLO analyzing frames…)
- Click the video → show event timeline with person/vehicle detection
- Show thumbnail images for each event

**Say:** "YOLO nano runs entirely locally. No GPU required — CPU only."

---

## 6. Live Camera / CCTV

**Demo:**
- Click Camera/CCTV button in the action bar (or Start Camera in Vision tab)
- Show status: RUNNING, detection_mode = yolo or motion_only
- Move in front of camera
- After a few seconds, show new "person detected" events in Timeline

**Say:** "Motion + object detection stores discrete events, not continuous video. Privacy-first."

---

## 7. Multi-Camera (Phase 16)

**Demo:**
- Go to Vision/CCTV tab → scroll to Multi-Camera Registry
- Add camera: Name="Front Door", Type=webcam, Index=0 → click Add Camera
- Click Start button on the new camera card
- Show it go LIVE with detection_mode

**Say:** "Named cameras. Webcam index, RTSP stream, or video file for replay testing."

---

## 8. Motion Predictions (Prediction Layer)

**Demo:**
- With camera running and YOLO active, scroll up to "Motion Predictions" panel
- Show tracked objects with direction arrows (→ ↗ ↙ ◉)
- Hover over prediction cards to see speed, trend, confidence

**Say:** "Linear velocity extrapolation. 1.5 second horizon. Heuristic, not guaranteed — honestly labeled."

---

## 9. Replay Studio (Phase 13)

**Demo:**
- Go to Replay tab
- Select "By Date" → pick today's date → Run Replay
- Show: summary card, key moments (debug_start, ai_research, etc.), chronological timeline

**Switch to:**
- "By Topic" → type "YOLO" → Run Replay
- Show topic-filtered chronological events

**Say:** "Replay anything — your whole day, a specific topic, or a single modality."

---

## 10. Digital Soul (Phase 14)

**Demo:**
- Go to Soul tab → click "Load Soul Profile"
- Show Behavioral Patterns: Coding Focus, Multi-Tool Workflow, etc.
- Show Workflow Rhythm: peak hours, day-of-week bar chart
- Show Project Memory: recurring projects, recent keywords, unfinished sessions

**Say:** "Analyzes only timestamps, app names, and keyword frequencies. Zero personal identity inference."

---

## 11. Neural Search (Phase 15)

**Demo:**
- Go to Timeline tab, search bar
- Type a complex query like "YOLO debugging FastAPI"
- (Note: neural search is available via POST /search/neural for developers)

**For API demo (Swagger):**
- Open http://localhost:8010/docs
- Find POST /search/neural
- Try: `{ "query": "person detected camera", "limit": 20 }`
- Show: answer_summary, grouped_by_modality, timeline, confidence

---

## 12. Agent Console (Phase 12)

**Demo:**
- Go to Agent tab
- Show Quick Actions grid: Open VSCode, Summarize Today, Search Memories, etc.
- Click "Summarize Today" → show daily summary with active hours, top apps
- Click "Search Memories" → show recent memories

**Say:** "Local-only actions. No shell injection. Allowlist only."

---

## 13. Memory Graph

**Demo:**
- Go to Graph tab
- Show nodes connected by: time, session, topic, app, semantic similarity
- Click a node to see its ego-graph

---

## 14. Sessions

**Demo:**
- Go to Sessions tab
- Show auto-detected work sessions
- Click a session → see all memories in that session
- Click Replay → show Phase 6 frame-by-frame replay player

---

## 13. World Model (Phase 17)

**Demo:**
- Go to Vision/CCTV tab → scroll to "World Model" panel
- Click "↺ Refresh World State"
- Show: world_state text + confidence %, active entity chips, zone grid, risk notes

**Say:** "The world model aggregates all camera events into a scene description.
All predictions are labeled [Estimated] — heuristic only, no false security claims."

---

## Summary

"EIDOLON OS is a fully local AI cognitive operating system. 20 phases implemented.
Zero cloud. Zero API keys. Everything on your machine."

API docs: http://localhost:8010/docs
