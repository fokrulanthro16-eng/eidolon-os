# EIDOLON OS — Final Checklist

## Backend Startup

- [ ] `uvicorn main:app --host 127.0.0.1 --port 8010 --reload` starts without errors
- [ ] GET /health returns `{"status": "ok"}`
- [ ] GET /docs shows Swagger UI with all routes
- [ ] Startup log shows all modules registered

## Existing Features (must not break)

- [ ] GET /memory/timeline returns memories list
- [ ] POST /memory/search returns results
- [ ] POST /memory/ingest-image accepts PNG/JPG
- [ ] POST /memory/ingest-pdf accepts PDF
- [ ] POST /pdf/chat answers PDF questions
- [ ] GET /sessions/list returns sessions
- [ ] GET /sessions/{id} returns session with memories
- [ ] GET /sessions/{id}/replay returns replay frames
- [ ] GET /export/memories returns JSON download
- [ ] GET /summary/daily returns summary

## New Endpoints

- [ ] POST /vision/ingest-video accepts MP4 (returns memory_id + video_id)
- [ ] POST /voice/ingest-audio accepts MP3/WAV (returns memory_id + transcript_available)
- [ ] GET /video/list returns video records
- [ ] GET /video/{id}/events returns event list
- [ ] GET /video/{id}/status returns {status, progress, event_count}
- [ ] GET /video/search?q=person returns matching events
- [ ] GET /graph/overview returns {nodes, edges, stats}
- [ ] GET /graph/memory/{id} returns ego-graph
- [ ] GET /graph/session/{id} returns session graph
- [ ] GET /profile/summary returns profile with privacy_note
- [ ] GET /suggestions returns up to 5 suggestions
- [ ] GET /suggestions/list alias works
- [ ] POST /suggestions/{id}/dismiss persists dismissal

## Frontend

- [ ] Timeline tab shows memory cards
- [ ] Sessions tab shows session list
- [ ] Videos tab shows upload button + video cards
- [ ] Graph tab shows nodes/edges table
- [ ] Profile tab shows insights + app usage
- [ ] Suggestions panel shows below search bar
- [ ] PDF upload button works
- [ ] Audio upload button works
- [ ] Video upload button works (in Videos tab)
- [ ] Search works for all types (screenshot, pdf, voice, video)
- [ ] TypeScript compiles without errors (`npx tsc --noEmit`)

## Fallback Behaviour

- [ ] App starts without any optional packages installed
- [ ] Video upload returns useful error when OpenCV missing
- [ ] Audio upload stores file even when Whisper missing
- [ ] Search works (keyword-only) without sentence-transformers
- [ ] PDF stores without PyMuPDF (no text extraction)

## Privacy / Security

- [ ] No API keys in code
- [ ] No cloud calls anywhere
- [ ] .gitignore includes storage/, .env, node_modules/, .next/
- [ ] .env.example has no real secrets
- [ ] Profile privacy_note is displayed in UI

## Performance

- [ ] Video analysis runs in background thread (does not block API)
- [ ] Embedding backfill runs in background thread on startup
- [ ] Suggestion cache invalidated on dismiss
- [ ] Profile cache expires after 60 seconds
- [ ] Graph overview capped at 120 nodes

## Known Limitations

- Video analysis is CPU-only (no GPU acceleration)
- YOLO nano has lower accuracy than larger models
- Graph uses edge cap per node (8 max) to prevent star explosion
- Voice transcription is synchronous (blocks request for audio duration)
- Semantic graph edges require embeddings to be pre-computed
