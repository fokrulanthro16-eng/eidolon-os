# EIDOLON OS — Release Notes

---

## v0.25.0 RC — Release Candidate
**Date:** 2026-05-31  
**Status:** Competition Ready — Google AI First Challenge 2026

### Phase 25 — Release Candidate Polish
- RC banner with competition-ready badge visible on dashboard
- Footer status strip: live memory count, session count, Gemini status, vision status, local-first indicator
- About dialog: project summary, key technologies, privacy architecture, local-first philosophy
- Judge Quick Facts card: 7 capability chips with hover descriptions
- All phases marked complete in FINAL_CHECKLIST.md

---

## v0.24.0 — Demo Polish + Judge Experience
**Date:** 2026-05-31

### Phase 24 — Judge UX
- Ask Eidolon quick-question chips visible at top of panel: Who am I? / What am I building? / What are my active projects? / What should I work on next? / What changed this week?
- 3-Minute Demo Flow card in Timeline tab with clickable tab navigation
- Run Demo Walkthrough button in Agent tab with expandable 5-step checklist
- "Timeline Analysis" renamed to "Behavior Trends"
- "Cognitive Profile" renamed to "Identity Profile"
- Empty state: "Start Screen Watch or Camera Monitoring to begin capturing memories"

---

## v0.22.0 — Identity Engine
**Date:** 2026-05-31

### Phase 22 — Identity
- Identity Engine: project detection from memory patterns, goal inference, 48-hour focus analysis
- Identity Snapshot card in Profile tab: primary project, current focus chips, active project chips, confidence score
- `/identity/profile`, `/identity/projects`, `/identity/next` endpoints
- 30-minute TTL identity cache in `storage/identity-db/`
- Identity reasoning: "Who am I?", "What am I building?", "What are my active projects?" now return synthesised answers grounded in project data, not memory title scans
- EIDOLON OS always surfaces as primary project in identity synthesis
- Local fallback via `local_identity_summary()` when Gemini unavailable

---

## v0.21.0 — Gemini Hybrid Layer
**Date:** 2026-05-30

### Phase 21 — Cloud AI Integration
- Google Gemini 2.0 Flash via `google-genai` SDK 1.74.0 (not deprecated `google-generativeai`)
- `BRAIN_PROVIDER=gemini` routes all chat through Gemini 2.0 Flash
- Streaming chat: SSE word-by-word via `/chat/stream`
- Agentic tool loop: up to 4 rounds of tool calling in `/brain/chat`
- Cognitive Core Orb: green = Gemini live, yellow = local fallback, red = backend down
- Profile Intelligence: Gemini-synthesised cognitive profile paragraph
- Trends Intelligence: 14-day activity chart, domain trend arrows, Gemini narrative
- Reasoning mode: identity/pattern questions auto-enrich context with recent memories
- Quota-safe fallback: structured error classification, local synthesis on quota hit
- `GEMINI_ALLOW_SYSTEM_LOCKDOWN=true` prevents any context leaving the device

---

## v0.20.0 — Core OS Complete
**Date:** 2026-05-25

### Phases 1–20 — Foundation
- OmniMemory: JSON memory store, timeline, session clustering
- NeuroVision: screenshot capture, Tesseract OCR, app fingerprinting (600+ patterns)
- SemanticEngine: hybrid BM25 + sentence-transformers vector search
- PDFBrain: PDF ingestion, chunking, semantic Q&A
- ReplayEngine: frame-by-frame session replay, smart replay 2.0
- DigitalProfile: behavioral profile, top apps, peak hours
- VoiceMemory: local faster-whisper transcription
- VideoIntelligence: YOLO nano object detection, event timeline
- MultiCamera: named camera registry, RTSP/webcam/file, isolated workers
- WorldModel: heuristic scene state, entity tracking, risk notes
- AgentMode: safe local action registry, open apps, summarize, search
- DigitalSoul: workflow rhythm, project memory, behavioral patterns
- NeuralSearch: cross-modal search with modality boosting
- TemporalGraph: memory relationship graph (same_session, near_time, same_app, same_topic)
- BrainRouter: local_semantic | Ollama | LM Studio | Gemini provider selection

---

## Architecture

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript 5 |
| Backend | Python 3.12, FastAPI 0.110 |
| Storage | JSON flat files (zero-dependency) |
| Search | sentence-transformers + BM25 |
| Vision | YOLOv8 nano (ultralytics) |
| Voice | faster-whisper (local) |
| Cloud AI (opt-in) | Google Gemini 2.0 Flash |
| Identity | python stdlib (Counter, defaultdict) |

---

## Upgrade Notes

### v0.24.0 → v0.25.0
No backend changes. Frontend only. Restart `npm run dev`.

### v0.22.0 → v0.24.0
No backend changes. Frontend only. Restart `npm run dev`.

### v0.21.0 → v0.22.0
New backend services: `identity_service.py`. New route: `identity.py`.  
Restart `uvicorn app.main:app --reload` after pulling.

### v0.20.0 → v0.21.0
New backend services: `gemini_bridge_service.py`, `gemini_tool_registry.py`, `intelligence_service.py`.  
New routes: `brain.py`, `intelligence.py`.  
Set `BRAIN_PROVIDER=gemini` and `GEMINI_API_KEY` in `apps/api/.env`.  
Install: `pip install google-genai`.
