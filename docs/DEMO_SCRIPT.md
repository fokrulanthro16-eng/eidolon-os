# EIDOLON OS — Demo Script v0.22.0

**Google AI First Challenge — Complete Walkthrough**

EIDOLON OS is a local-first AI cognitive operating system that captures your digital activity and lets you reason about it using Google Gemini. This script walks through every major feature in a logical narrative order.

Estimated time: **12–18 minutes** for a full run. Skip to the sections marked ⭐ for a 5-minute highlight reel.

---

## Before You Start

### 1. Get a Gemini API Key (free)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API key** — no credit card required
3. Copy the key (starts with `AIza...`)

### 2. Configure `.env`

Open `apps/api/.env` and set:

```ini
BRAIN_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...your_key_here
GEMINI_MODEL=gemini-2.0-flash
GEMINI_ALLOW_SYSTEM_LOCKDOWN=false
```

### 3. Install dependencies

```powershell
cd apps\api
pip install -r requirements.txt
```

Optional but recommended for full demo:

```powershell
pip install pymupdf faster-whisper sentence-transformers
pip install opencv-python-headless ultralytics numpy
```

---

## Step 1 — Start the Backend ⭐

```powershell
cd apps\api
.venv-312\Scripts\Activate.ps1   # or .venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Watch for the startup banner:

```
━━━ EIDOLON OS  1.0.0  [Phase 21 — Gemini Hybrid] ━━━
OCR:     tesseract ✓ (or ✗ — optional)
Search:  sentence-transformers ✓  (hybrid keyword+semantic)
PDF:     PyMuPDF ✓
Voice:   faster-whisper ✓
Video:   OpenCV ✓  YOLO nano ✓
Brain:   BRAIN_PROVIDER=gemini  key=set  model=gemini-2.0-flash
Memory:  0 item(s) loaded
```

> If you see `key=set`, Gemini is configured. If you see `key=missing`, re-check `.env`.

---

## Step 2 — Start the Frontend ⭐

```powershell
cd apps\web
npm run dev
```

Open **http://localhost:3000** — you should see the dark EIDOLON OS dashboard.

---

## Step 3 — Observe the Cognitive Core Orb ⭐

Look at the **top-right of the header**. You will see a pulsing orb:

| Color | Meaning |
|-------|---------|
| 🟢 **Green** | Gemini is live — all chat answers use Gemini |
| 🟡 **Yellow** | Local fallback — Gemini quota exceeded or no key set |
| 🔴 **Red** | Backend unreachable — check port 8010 |

The orb polls `/brain/status` every 30 seconds and updates immediately after each chat message. Hover over it to see the tooltip: provider, mode, and any quota details.

**What to say during demo:** *"This orb is EIDOLON's Cognitive Core — a real-time status indicator. Green means Gemini is thinking. Yellow means it's running entirely on-device with no cloud. Red means the backend is down. No ambiguity."*

---

## Step 4 — Ask Eidolon: Identity Question ⭐

Click **⬡ ASK EIDOLON** (the collapsible panel below the search bar).

Type: `Who are you?`

**Expected Gemini response:**
> "I am EIDOLON OS — a local-first AI cognitive assistant running on your machine. I help you recall and understand your digital activity by searching through your captured memories, screenshots, documents, and camera events. Unlike cloud-first tools, everything I know about you stays on your device..."

Notice:
- The answer streams **word by word** (not all at once)
- The footer shows **⬡ Gemini** in violet
- No "searched:" or "0 mem" metadata — it's a reasoning answer, not a search result

---

## Step 5 — Upload a PDF ⭐

1. Click **⊕ Upload PDF** in the search bar area
2. Select any PDF (research paper, manual, API documentation)
3. The PDF appears in the Timeline as an orange card with page count

### Ask the PDF

1. Click **◫ Ask PDF** on the PDF card
2. The PDF Chat panel slides in from the right
3. Type: *"What is the main topic of this document?"*
4. See the answer with:
   - Confidence score
   - Source page numbers
   - Matched text chunks (expandable)
5. Try: *"What are the key conclusions?"*

> PDFs are chunked locally — no content leaves your machine unless Gemini is enabled.

---

## Step 6 — Start the Screen Watcher

In a new terminal:

```powershell
cd apps\api
.venv-312\Scripts\Activate.ps1
python -m app.workers.screen_watcher
```

Wait 30 seconds — a screenshot memory appears in the Timeline.

Switch between apps (browser → code editor → terminal) to generate varied memories. Each memory gets:
- OCR text (if Tesseract installed)
- App fingerprint (VSCode / Chrome / Terminal etc.)
- Scene type + probable task (e.g. "Software Development")
- Vision Intelligence tags

**What to say:** *"Every 30 seconds, EIDOLON quietly takes a screenshot, extracts text via OCR, identifies the app and workflow type, and stores it locally. No cloud. No upload. Just your machine learning about itself."*

---

## Step 7 — Search Memories ⭐

1. Type any keyword in the search bar: `python`, `camera`, `browser`
2. Press **Search**
3. See results ranked by hybrid score (semantic + keyword + recency)
4. Notice the **⬡ semantic** / **⬡ keyword** badge on each card
5. Click **Clear** to return to the full timeline

---

## Step 8 — Vision / CCTV Memory Capture ⭐

### Option A — Upload a Video

1. Click the **⬡ Vision / CCTV** tab
2. Click **⊕ Upload Video** and select an MP4/AVI/MOV file
3. Watch the status badge: `PENDING → ANALYZING 23% → DONE`
4. Click the video card to open the event timeline
5. See detected events: `person appeared`, `object detected`, `motion detected`
6. Each event has a timestamp offset and thumbnail

### Option B — Live Webcam

1. On the Vision/CCTV tab, scroll to the **Live Camera** section
2. Click **Start** to begin webcam detection
3. Move in front of the camera
4. Watch events appear in the panel: `Person detected`, `Object stationary`
5. Open the **◈ Timeline** tab — camera events are now searchable memories

### Multi-Camera (named cameras)

1. Click **⊕ Add Camera** under the Multi-Camera section
2. Enter a name (e.g. `Front Door`) and a webcam index (`0`) or RTSP URL
3. Start it — EIDOLON runs a separate worker thread per camera
4. Each camera stream generates events independently

**What to say:** *"EIDOLON sees what your cameras see. Person detection, object tracking, stationary alerts — all processed locally via YOLO nano. No cloud vision API. No footage sent anywhere."*

---

## Step 9 — World Model

1. After some camera events are captured, click the **World Model** section on the Vision tab
2. See the heuristic world-state:
   - Active entities (persons, objects, vehicles)
   - Zone assignments
   - Recent event timeline
   - Risk notes (e.g. "Object stationary for >5 min")
   - Movement predictions `[Estimated]`

---

## Step 10 — Agent Dashboard ⭐

1. Click the **⬡ Agent** tab
2. See the available local actions:
   - **Summarize Today** — generates a daily activity summary
   - **Open VSCode** — launches VSCode via subprocess
   - **Continue Last Session** — resumes the most recent work context
   - **What Am I Working On** — uses the workflow engine
3. Click **Summarize Today** → see the summary generated from your memories
4. See the **Workflow Periods** section — blocks of time by app + activity type

---

## Step 11 — Ask Eidolon: Memory Reasoning ⭐

In the **⬡ ASK EIDOLON** panel, try these questions:

### Grounded factual recall

```
What was I working on earlier?
What documents did I open today?
What apps have I used most?
```

**What happens:** EIDOLON retrieves relevant memories (keyword + semantic search), passes them to Gemini as context, and synthesises a paragraph — not a list of search results.

### Identity questions (Phase 22 — Identity Engine) ⭐

```
Who am I?
What am I building?
What are my active projects?
What should I work on next?
```

**What happens:** EIDOLON detects the identity intent, loads the cached Identity Engine context (projects, focus, goals, suggested next), injects it alongside recent memories, and asks Gemini to synthesise a specific answer about the user's work — not a generic memory dump.

**Expected response style:**
> "You appear to be building EIDOLON OS, a local-first AI cognitive operating system. Your recent work focuses on Gemini integration, camera intelligence, memory reasoning, and agent workflows. Your active projects include the Gemini Hybrid Layer and Camera & Vision System. Based on your recent activity, you should continue building out the identity synthesis and profile intelligence layers."

### Reasoning questions (pattern mode)

```
Who am I based on the memories you have?
What patterns do you see in my work?
Summarize my recent activity.
```

**What happens:** EIDOLON detects the reasoning intent, automatically loads the most recent memories regardless of keyword match, uses the `REASONING` system prompt, and asks Gemini to infer patterns.

### Quota fallback (if quota exceeded)

If the yellow orb appears, ask any question. You will see:
- A Gemini-badge response that uses local memory + identity synthesis
- The status: `Gemini limited · local fallback active · retry in Xs`
- A still-useful answer — never a crash or blank screen

---

## Step 12 — Profile Intelligence ⭐

1. Click the **◉ Profile** tab
2. The tab loads in three layers:

**Identity Snapshot (Phase 22 — top card):** ⭐
- **Project statement**: "You appear to be building EIDOLON OS..." — synthesised from the Identity Engine
- **Current Focus chips**: Technical domains from the last 48 hours of activity
- **Active Project chips**: Color-coded by status (emerald = active, yellow = recent)
- **Confidence score + memory count** in the header

**Identity Card (Phase 22 — full detail):**
- Full Gemini-synthesised identity paragraph
- Active projects with confidence bars
- Inferred goals list
- "What should I work on next?" suggestion

**Cognitive Profile (Phase 21 — below):**
- **Gemini summary paragraph**: 3–5 sentences describing activity patterns
- **Primary Activities**: domain activity bars with percentages
- **Recurring Keywords**: topic chips from memory content
- **Proactive Insights**: 5–6 auto-generated insight cards

**Behavioral Profile (base layer):**
- Top apps, workflow patterns, memory type distribution, peak hours

**What to say:** *"That first card is Phase 22 — the Identity Engine. It reads all my memories, detects active projects by keyword pattern, infers goals, calculates focus from recent 48-hour activity, and writes a synthesis paragraph with Gemini. It knows I'm building EIDOLON OS — not because I told it, but because that's what the memories show."*

---

## Step 13 — Trends Intelligence ⭐

1. Click the **◷ Trends** tab
2. See:
   - **Timeline narrative**: Gemini-written paragraph summarising the week
   - **Three summary cards**: This Week / Last Week / All Time counts
   - **14-day activity bar chart**: Each bar represents one day's memory count. Hover for the exact count and date.
   - **Domain Trends**: Arrows for each area — ↑ rising, → stable, ↓ falling — with week-over-week percentage change
   - **Memory Clusters**: Horizontal bars showing how the 14-day window distributes across domains

**Example trend narrative:**
> "You captured 8 memories this week — up 300% compared to last week's 2. Camera & Vision activity is trending sharply upward, accounting for most of this increase. Tuesday was your most active day with 4 events captured."

**What to say:** *"This isn't just a chart — Gemini synthesised that paragraph from the raw counts. It notices patterns a dashboard would just display as numbers."*

---

## Step 14 — Session Replay

1. Click the **◫ Sessions** tab
2. Sessions are auto-detected from memory clusters (gap-based algorithm)
3. Click a session card to see all memories in that session
4. Click **▶ Replay** to open the Replay overlay:
   - Arrow keys to advance frames
   - Space to auto-play at 2-second intervals
   - Scroll bar for scrubbing
   - App badge + OCR text panel on the right
5. Press Escape to close

---

## Step 15 — Memory Graph

1. Click the **◎ Graph** tab
2. See memory relationships:
   - `same_session` — memories captured in the same work session
   - `near_time` — memories within minutes of each other
   - `same_app` — same application detected
   - `same_topic` — shared keywords
   - `workflow_related` — same workflow classification
3. Each edge row shows: from memory → relationship type → to memory

---

## Step 16 — Digital Soul

1. Click the **◉ Soul** tab
2. See:
   - Hourly activity heatmap — when you're most active each day
   - Workflow rhythm — peak hours and most active day of week
   - Project memory — top projects, recent keywords, unfinished sessions
   - Behavioral patterns — inferred patterns with strength scores

---

## Step 17 — Voice Memory (if faster-whisper installed)

1. Click **⊕ Upload Audio** in the search bar area
2. Select an MP3/WAV/M4A file (a meeting recording, voice note, etc.)
3. Whisper transcribes it locally — no API call
4. The transcript appears as a voice memory card with:
   - Language detected
   - Transcript confidence
   - Searchable text
5. Search for any word from the transcript

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Orb is red | Backend not running — start with `python -m uvicorn app.main:app --reload --port 8010` |
| Orb is yellow, key is set | Free-tier quota exceeded — wait ~24h or use a new key |
| No memories appear | Start screen watcher: `python -m app.workers.screen_watcher` |
| Ask Eidolon shows local text | Check `BRAIN_PROVIDER=gemini` in `.env`, restart backend |
| Video stuck at ANALYZING | Install opencv: `pip install opencv-python-headless ultralytics` |
| No transcript on audio | Install faster-whisper: `pip install faster-whisper` |
| PDF shows no text | Install pymupdf: `pip install pymupdf` |
| Backend import error | Use `app.main:app` not `main:app` in uvicorn command |
| `app.main` not found | Run from `apps/api/` directory, not from repo root |

---

## Google AI First Challenge — Narrative Summary

**The problem:** Your computer generates thousands of moments of context every day — screenshots, documents, audio, video. None of it is searchable. None of it can answer questions. It just disappears.

**EIDOLON OS captures all of it** and stores it locally as structured memories. No cloud upload. No account. No privacy risk.

**Phase 21 adds Google Gemini** as an optional cognitive layer. When enabled:
- Every question you ask is answered by Gemini using your actual memories as context
- Your accumulated history is synthesised into a cognitive profile
- Weekly patterns are identified and narrated automatically
- Reasoning questions ("Who am I?", "What changed this week?") trigger memory-enriched Gemini inference

**Phase 22 adds the Identity Engine.** EIDOLON now knows who you are and what you're building:
- Detects active projects from memory patterns (EIDOLON OS, Gemini Hybrid Layer, Camera & Vision...)
- Infers goals from keyword signals across all memories
- Determines current focus from the last 48 hours of activity
- Answers "Who am I?", "What am I building?", "What should I work on next?" with synthesised reasoning
- The Identity Snapshot card gives a compact at-a-glance summary on every Profile tab load

**The local-first guarantee remains absolute.** Gemini is opt-in. Every feature works without it. If Gemini hits quota, local synthesis takes over transparently. The orb tells you which mode you're in at all times.

**EIDOLON OS is not a search engine. It is a cognitive operating system.**

---

*EIDOLON OS v0.22.0 — Phase 22: Identity Engine · Local-First · Google AI First Challenge 2026*
