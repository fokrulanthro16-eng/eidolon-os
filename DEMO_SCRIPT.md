# EIDOLON OS — Demo Script

A step-by-step walkthrough for demonstrating or evaluating EIDOLON OS.
Estimated time: 10–15 minutes.

---

## Prerequisites

- Backend running: `uvicorn main:app --host 127.0.0.1 --port 8010 --reload`
- Frontend running: `npm run dev`
- Browser open at http://localhost:3000

---

## Step 1 — Start Backend

```bash
cd apps/api
.venv\Scripts\activate   # Windows
uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

Watch for startup diagnostics:
```
━━━ EIDOLON OS  1.0.0  [Phase 10 — Video Intelligence] ━━━
OCR:     tesseract ✓
Search:  sentence-transformers ✓  (hybrid keyword+semantic)
PDF:     PyMuPDF ✓
Voice:   faster-whisper ✓
Video:   OpenCV ✓  YOLO nano ✓
Graph:   temporal memory graph active
Memory:  0 item(s) loaded from store
```

---

## Step 2 — Start Frontend

```bash
cd apps/web
npm run dev
```

Open http://localhost:3000 — you should see the dark EIDOLON OS dashboard.

---

## Step 3 — Upload a PDF

1. Click **⊕ Upload PDF** in the search bar area
2. Select any PDF (research paper, manual, documentation)
3. The PDF appears in the Timeline as an orange card
4. Hover over it to see the PDF icon

---

## Step 4 — Ask the PDF

1. Click **◫ Ask PDF** on the PDF card
2. The PDF Chat panel slides in from the right
3. Type: *"What is the main topic of this document?"*
4. Press Enter or click **Ask**
5. See the answer with confidence score and source pages
6. Try the sample questions below the input

---

## Step 5 — Start Screen Watcher

In a new terminal:
```bash
cd apps/api
.venv\Scripts\activate
python -m app.workers.screen_watcher
```

Wait 30 seconds — a screenshot memory will appear in the Timeline.
Try switching apps (browser → editor → terminal) to generate varied memories.

---

## Step 6 — Search Memories

1. Type any keyword in the search bar (e.g., "python", "browser", "error")
2. Press Search
3. See hybrid keyword + semantic results
4. Notice the **⬡ semantic** / **⬡ keyword** badge in the header
5. Click **Clear** to return to the full timeline

---

## Step 7 — View Sessions

1. Click the **◫ Sessions** tab
2. See automatically-detected work sessions
3. Click a session card to open its detail view
4. See all memories from that session in a grid

---

## Step 8 — Replay a Session

1. From the Sessions tab, click the **▶ Replay** button on any session
2. The Replay overlay opens
3. Use arrow keys or buttons to advance frames
4. Press Space to auto-play
5. Press Escape to close

---

## Step 9 — Upload a Video (if opencv installed)

1. Click the **⬡ Videos** tab
2. Click **⊕ Upload Video**
3. Select any MP4/AVI/MOV video
4. Watch the status badge change from PENDING → ANALYZING XX% → DONE
5. Click the video card to see the event timeline
6. Filter events by type (person / motion / crowd)
7. Try the search: *"person appeared"* in the timeline

---

## Step 10 — Upload Audio (if faster-whisper installed)

1. Click **⊕ Upload Audio** in the search bar area
2. Select an MP3/WAV/M4A file
3. The audio is transcribed locally
4. The transcript appears as a voice memory card
5. Search for words from the transcript

---

## Step 11 — View Memory Graph

1. Click the **◎ Graph** tab
2. See the memory connection overview
3. Read edge types: same_session (blue), near_time (gold), same_app (green),
   same_topic (purple), workflow_related (orange)
4. Each row shows: from memory → relationship → to memory

---

## Step 12 — View Digital Soul Profile

1. Click the **◉ Profile** tab
2. See: top apps, active hours, peak period, workflow patterns
3. Read the privacy note at the top
4. See recurring topics, type distribution, productivity notes

---

## Step 13 — Autonomous Suggestions

1. Scroll up — look for the **⬡ EIDOLON INSIGHTS** panel below the search bar
2. See up to 5 grounded suggestions based on your captured memories
3. Click **×** to dismiss any suggestion (persisted to disk)
4. Suggestions regenerate as you add more memories

---

## Troubleshooting

| Issue | Fix |
|---|---|
| No memories appear | Start screen watcher or upload a file |
| Video stuck at ANALYZING | Check if opencv is installed |
| No transcript on audio | Install faster-whisper |
| Search returns no results | Try shorter keywords |
| Backend unreachable | Check port 8010 is not blocked |
