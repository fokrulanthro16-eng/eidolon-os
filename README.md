<div align="center">

```
███████╗██╗██████╗  ██████╗ ██╗      ██████╗ ███╗   ██╗      ██████╗ ███████╗
██╔════╝██║██╔══██╗██╔═══██╗██║     ██╔═══██╗████╗  ██║     ██╔═══██╗██╔════╝
█████╗  ██║██║  ██║██║   ██║██║     ██║   ██║██╔██╗ ██║     ██║   ██║███████╗
██╔══╝  ██║██║  ██║██║   ██║██║     ██║   ██║██║╚██╗██║     ██║   ██║╚════██║
███████╗██║██████╔╝╚██████╔╝███████╗╚██████╔╝██║ ╚████║     ╚██████╔╝███████║
╚══════╝╚═╝╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝      ╚═════╝ ╚══════╝
```

### Your computer's cognitive operating system. Local-first. Gemini-powered. No compromise.

<br/>

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://aistudio.google.com/)
[![Platform](https://img.shields.io/badge/platform-Windows%2011-0078D6?style=flat-square&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Local First](https://img.shields.io/badge/local--first-always%20works-10D984?style=flat-square)](#privacy)
[![Phase](https://img.shields.io/badge/phase-25%20%E2%80%94%20Release%20Candidate-10D984?style=flat-square)](#roadmap)
[![Version](https://img.shields.io/badge/version-v0.25.0%20RC-10D984?style=flat-square)](#release-notes)
[![License](https://img.shields.io/badge/license-MIT-F59E0B?style=flat-square)](LICENSE)

<br/>

**[Demo Script](docs/DEMO_SCRIPT.md) · [Architecture](docs/ARCHITECTURE.md) · [Privacy Policy](docs/PRIVACY.md) · [Roadmap](docs/ROADMAP.md) · [Setup Guide](docs/SETUP_WINDOWS.md)**

</div>

---

<br/>

> **EIDOLON OS** is an open-source, Windows-native AI cognitive operating system that captures everything you do — screenshots, documents, audio, video, camera feeds — and makes it all **searchable, replayable, and intelligently reasoned**. Runs fully offline by default. Optionally upgrades to **Google Gemini** for natural-language synthesis and cognitive profile generation. Zero cloud lock-in. Everything lives on your machine.

<br/>

---

## What's New in v0.25.0 RC — Release Candidate

Phase 25 prepares EIDOLON OS for final competition submission:

| Feature | Description |
|---------|-------------|
| **RC Banner** | "EIDOLON OS v0.25.0 RC — Competition Ready" banner with dismissible × and About button |
| **Footer Status Strip** | Fixed footer: live memory count, session count, Gemini status, vision status, local-first indicator |
| **About Dialog** | Full project summary, key technologies, privacy architecture, local-first philosophy |
| **Judge Quick Facts** | 7 capability chips in the Timeline tab with hover descriptions (Local AI, Vision, Voice, PDF, Memory Graph, Identity Engine, Gemini Hybrid) |
| **RELEASE_NOTES.md** | Full version history from v0.20.0 → v0.25.0 |
| **FINAL_CHECKLIST.md** | All 25 phases marked complete |

---

## What's New in v0.22.0 — Identity Engine

Phase 22 adds a persistent identity layer that answers the questions a cognitive OS should always know:

| Feature | Description |
|---------|-------------|
| **Identity Engine** | Analyses accumulated memories to detect active projects, infer goals, and determine current focus. Rebuilt every 30 minutes and cached. |
| **"Who Am I?" Reasoning** | Asking "Who am I?", "What am I building?", or "What should I work on next?" returns a synthesised identity paragraph — not a search-result dump. |
| **Identity Snapshot Card** | Compact at-a-glance card in the Profile tab: primary project, current focus chips, active project chips, confidence score. |
| **Project Detection** | Keyword-pattern matching across all memories detects named projects (EIDOLON OS, Gemini Hybrid Layer, Camera & Vision System, etc.) with confidence scores and recency status. |
| **Goal Inference** | Automatically infers up to 5 user goals from memory content patterns. |
| **Next Suggestion** | Gemini-powered "What should I work on next?" recommendation based on active projects and current focus. |
| **Identity API** | Three new endpoints: `/identity/profile`, `/identity/projects`, `/identity/next`. All backed by a 30-min TTL cache. |

---

## What's New in v0.21.0 — Gemini Hybrid Layer

Phase 21 transforms EIDOLON from a memory-retrieval tool into a **cognitive operating system**:

| Feature | Description |
|---------|-------------|
| **Gemini Hybrid Brain** | Google Gemini 2.0 Flash synthesises natural-language answers from local memories. Set `BRAIN_PROVIDER=gemini` in `.env`. Falls back to `local_semantic` automatically if the key is absent or quota-limited. |
| **Cognitive Core Orb** | Live status indicator in the UI header. Green = Gemini active. Yellow = local fallback or quota limited. Red = backend unreachable. Updates every 30 s and immediately after each chat. |
| **Profile Intelligence** | Gemini-synthesised cognitive profile: domain activity bars, active projects, inferred interests, proactive insights — all derived from accumulated memories. |
| **Trends Intelligence** | 14-day activity chart, week-over-week deltas, domain trend arrows (↑ rising / → stable / ↓ falling), and memory cluster distribution. |
| **Reasoning Mode** | Questions like *"Who am I?"*, *"What patterns do you see?"*, *"Summarize my week"* automatically enrich context with recent memories and trigger the Gemini pattern-inference prompt — no keyword search required. |
| **Ask Eidolon** | The main chat panel (`⬡ ASK EIDOLON`) now routes through Gemini when configured. Responses are streamed word-by-word with a `⬡ Gemini` footer badge. |
| **Quota-Safe Fallback** | When Gemini hits free-tier limits, the system surfaces a `quota_exceeded` status, shows the retry window, and continues answering from local memory — never crashes, never returns blank. |

---

## Screenshots

<div align="center">

| Cognitive Core Orb | Ask Eidolon (Gemini) | Profile Intelligence |
|:-:|:-:|:-:|
| <img src="docs/assets/screenshot-orb.png" alt="Orb" width="280"/> | <img src="docs/assets/screenshot-chat.png" alt="Chat" width="280"/> | <img src="docs/assets/screenshot-profile.png" alt="Profile" width="280"/> |
| *Live Gemini status in header* | *Streamed Gemini reasoning answers* | *Domain bars · projects · insights* |

| Trends Intelligence | Vision/CCTV | Agent Dashboard |
|:-:|:-:|:-:|
| <img src="docs/assets/screenshot-trends.png" alt="Trends" width="280"/> | <img src="docs/assets/screenshot-vision.png" alt="Vision" width="280"/> | <img src="docs/assets/screenshot-agent.png" alt="Agent" width="280"/> |
| *14-day chart · domain trends · clusters* | *YOLO detection · World Model* | *Local actions · Brain Chat* |

> 📸 Run `.\scripts\start_all.ps1` and open http://localhost:3000 to see the live UI.

</div>

---

## Feature Matrix

<table>
<thead>
<tr>
<th>Module</th>
<th>Phase</th>
<th>What It Does</th>
<th>Requires</th>
<th>Status</th>
</tr>
</thead>
<tbody>
<tr><td><b>OmniMemory</b></td><td>1–3</td><td>JSON memory store · session clustering · timeline</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>NeuroVision</b></td><td>2</td><td>Screenshot capture · OCR text extraction · window detection</td><td>pytesseract <em>(optional)</em></td><td>✅ Core</td></tr>
<tr><td><b>SemanticEngine</b></td><td>4</td><td>Hybrid keyword + vector search across all memory types</td><td>sentence-transformers <em>(optional)</em></td><td>✅ Core</td></tr>
<tr><td><b>PDFBrain + PDFChat</b></td><td>5</td><td>PDF ingestion · chunk extraction · natural language Q&A</td><td>pymupdf <em>(optional)</em></td><td>✅ Core</td></tr>
<tr><td><b>ReplayEngine</b></td><td>6</td><td>Frame-by-frame session replay player</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>DigitalProfile</b></td><td>7</td><td>Behavioral profile from memory metadata · top apps · peak hours</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>AutoSuggestions</b></td><td>8</td><td>Grounded autonomous suggestions · no hallucination</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>VoiceMemory</b></td><td>9</td><td>Audio upload → local Whisper transcription → searchable memory</td><td>faster-whisper <em>(optional)</em></td><td>✅ Core</td></tr>
<tr><td><b>VideoIntelligence</b></td><td>10</td><td>Video upload · YOLO nano object detection · event timeline · live CCTV</td><td>opencv + ultralytics <em>(optional)</em></td><td>✅ Core</td></tr>
<tr><td><b>VisionIntelligence</b></td><td>11</td><td>App fingerprinting (600+ patterns) · workflow type · smart titles</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>AgentMode</b></td><td>12</td><td>Safe local action registry · open apps · summarize · search</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>ReplayEngine 2.0</b></td><td>13</td><td>Replay by date / topic / modality · key moment detection</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>DigitalSoul</b></td><td>14</td><td>Workflow rhythm · project memory · behavioral patterns</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>NeuralSearch</b></td><td>15</td><td>Cross-modal neural search · grouped by modality · answer summary</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>MultiCamera</b></td><td>16</td><td>Named camera registry · RTSP / webcam / file · isolated workers</td><td>opencv <em>(optional)</em></td><td>✅ Core</td></tr>
<tr><td><b>WorldModel</b></td><td>17</td><td>Heuristic scene state · active entities · zone mapping · risk notes</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>BrainRouter</b></td><td>18</td><td>Brain provider selection: local_semantic · Ollama · LM Studio · Gemini</td><td>Ollama / LMStudio / Gemini key <em>(all optional)</em></td><td>✅ Core</td></tr>
<tr><td><b>TemporalGraph</b></td><td>9+</td><td>Memory relationship graph · time / session / topic / app edges</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>PredictionLayer</b></td><td>10+</td><td>Live CCTV trajectory prediction · direction · speed · [Estimated]</td><td>opencv + ultralytics</td><td>✅ Core</td></tr>
<tr><td><b>GeminiBridge</b></td><td>21</td><td>Google Gemini 2.0 Flash hybrid brain · streaming answers · agentic tool loop</td><td>Free Google AI Studio key <em>(optional)</em></td><td>✅ Shipped</td></tr>
<tr><td><b>Profile Intelligence</b></td><td>21</td><td>Gemini-synthesised cognitive profile · domain bars · projects · proactive insights</td><td>—</td><td>✅ Shipped</td></tr>
<tr><td><b>Trends Intelligence</b></td><td>21</td><td>14-day activity chart · week-over-week trends · memory clustering by domain</td><td>—</td><td>✅ Shipped</td></tr>
<tr><td><b>Identity Engine</b></td><td><b>22</b></td><td>Project detection · goal inference · focus analysis · "Who am I?" synthesis · identity cache</td><td>—</td><td>✅ <b>New</b></td></tr>
<tr><td><b>Identity Snapshot</b></td><td><b>22</b></td><td>Compact Profile tab card · primary project · focus chips · active project chips · confidence</td><td>—</td><td>✅ <b>New</b></td></tr>
<tr><td><b>Desktop Shell</b></td><td>23+</td><td>Tauri / Electron native wrapper · system tray · auto-start</td><td>Rust toolchain</td><td>🗺 Planned</td></tr>
</tbody>
</table>

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           EIDOLON OS  v0.21.0                                │
│                                                                              │
│   ┌─────────────────────────┐   HTTP/JSON   ┌──────────────────────────────┐│
│   │   Next.js 16  (: 3000)  │◄─────────────►│   FastAPI backend  (: 8010)  ││
│   │   React 19  TypeScript  │               │                              ││
│   │                         │               │  ┌──────────┐  ┌──────────┐  ││
│   │  Tabs:                  │               │  │  Routes  │  │ Services │  ││
│   │   Timeline  Sessions    │               │  │  23 mods │  │  36 mods │  ││
│   │   Vision    Replay      │               │  └────┬─────┘  └────┬─────┘  ││
│   │   Soul      Graph       │               │       └──────┬───────┘        ││
│   │   Profile   Trends      │               │              ▼                ││
│   │   Agent     Brain Chat  │               │   ┌──────────────────────┐   ││
│   └──────────┬──────────────┘               │   │   Local Storage      │   ││
│              │                              │   │   storage/           │   ││
│              │  Cognitive Core Orb          │   │   ├─ memory-db/      │   ││
│              │  ● Green  = Gemini live       │   │   ├─ session-db/     │   ││
│              │  ● Yellow = Local fallback    │   │   ├─ screenshots/    │   ││
│              │  ● Red    = Backend down      │   │   ├─ uploads/        │   ││
│                                             │   │   ├─ videos/         │   ││
│                                             │   │   └─ cameras/        │   ││
│   ┌──────────────────────────────────────┐  │   └──────────────────────┘   ││
│   │  Gemini Hybrid Layer  (optional)     │  └──────────────────────────────┘│
│   │                                      │                                  │
│   │  GeminiBridgeService                 │   ┌──────────────────────────┐   │
│   │  ├─ generate_with_history()          │   │  Intelligence Service    │   │
│   │  ├─ generate_stream()               │   │  ├─ cluster_memories()   │   │
│   │  ├─ generate_from_prompt()          │   │  ├─ analyze_timeline()   │   │
│   │  └─ local_fallback() ← always safe  │   │  ├─ generate_insights()  │   │
│   │                                      │   │  └─ build_profile_ctx() │   │
│   │  google-genai SDK (1.74.0)           │   └──────────────────────────┘   │
│   │  ↕ aistudio.google.com (opt-in)      │                                  │
│   └──────────────────────────────────────┘                                  │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Optional local LLMs (also work as brain providers)                  │  │
│   │  Ollama :11434  ·  LM Studio :1234                                   │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Background Workers (daemon threads)                                 │  │
│   │  screen_watcher · camera_worker(s) · video_analyzer · embed_backfill │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘

        No mandatory internet. No database server. No auth service.
        Gemini is opt-in. Local semantic fallback always active.
```

**Full docs:** [Architecture](docs/ARCHITECTURE.md) · [System Flow](docs/SYSTEM_FLOW.md) · [Phase Log](docs/PHASES.md)

---

## Privacy

<div align="center">

```
╔══════════════════════════════════════════════════════════════════╗
║               WHAT EIDOLON OS DOES WITH YOUR DATA               ║
╠══════════════════════════════════════════════════════════════════╣
║  ✅  Stores everything locally in storage/ on your machine       ║
║  ✅  Processes all AI locally — OCR, Whisper, YOLO, embeddings   ║
║  ✅  Optional LLM runs on localhost (Ollama / LM Studio)         ║
║  ✅  You can delete everything: rm -rf storage/                  ║
║  ✅  Gemini is opt-in — disabled by default, zero-config mode    ║
║  ✅  Gemini fallback always available — never a hard dependency   ║
╠══════════════════════════════════════════════════════════════════╣
║  ❌  Never sends data to the internet without your opt-in        ║
║  ❌  No telemetry, analytics, or crash reporting                 ║
║  ❌  No account, login, or subscription required                 ║
║  ❌  No continuous video recording (events only)                 ║
╚══════════════════════════════════════════════════════════════════╝
```

</div>

**Gemini note:** When `BRAIN_PROVIDER=gemini` is set, memory context snippets (not raw screenshots or files) are sent to the Gemini API to generate answers. Gemini is never enabled by default. All features work without it.

All data lives in `storage/` at the project root. You own it completely. See [docs/PRIVACY.md](docs/PRIVACY.md) for the full policy.

---

## Installation

### Prerequisites

| Requirement | Version | Download |
|-------------|---------|----------|
| Python | **3.12.x** | [python.org](https://www.python.org/downloads/) |
| Node.js | **18+ LTS** | [nodejs.org](https://nodejs.org/) |
| Git | any | [git-scm.com](https://git-scm.com/) |

### Quick Start

```powershell
# 1. Clone
git clone https://github.com/your-username/eidolon-os.git
cd eidolon-os

# 2. Python virtual environment
py -3.12 -m venv .venv-312
.venv-312\Scripts\Activate.ps1

# 3. Install backend dependencies
cd apps\api
pip install -r requirements.txt

# 4. Environment file
cd ..\..
Copy-Item apps\api\.env.example apps\api\.env   # edit if needed

# 5. Frontend
cd apps\web
npm install
```

### Running the App

```powershell
# One-command launch
.\scripts\start_all.ps1
```

Or manually in two terminals:

```powershell
# Terminal 1 — API (note: must use app.main:app)
cd apps\api
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010

# Terminal 2 — Frontend
cd apps\web
npm run dev
```

| Service | URL |
|---------|-----|
| **Dashboard** | http://localhost:3000 |
| **API Swagger** | http://127.0.0.1:8010/docs |
| **API ReDoc** | http://127.0.0.1:8010/redoc |

> **Execution policy error?** Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

---

## Optional AI Features

Everything below is **opt-in**. EIDOLON OS runs fully without any of them.

### Gemini Hybrid Brain (Phase 21)

Get a free API key at [aistudio.google.com](https://aistudio.google.com/app/apikey) — no credit card required.

```ini
# apps/api/.env
BRAIN_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...your_key_here
GEMINI_MODEL=gemini-2.0-flash
```

Restart the backend. The Cognitive Core Orb in the header turns **green** when Gemini is live. If the key is absent or quota is exceeded, the orb turns **yellow** and all answers fall back to `local_semantic` automatically — no crash, no blank response.

The Gemini integration provides:
- **Ask Eidolon** — streamed natural-language answers grounded in your memories
- **Cognitive Profile** — synthesised paragraph describing your activity patterns
- **Timeline Narrative** — natural-language summary of weekly trends
- **Reasoning Mode** — identity questions ("Who am I?", "What patterns?") enrich context with recent memories automatically

### Local OCR, PDF, Vector Search, Voice, Vision

```powershell
pip install pymupdf                  # PDF text extraction
pip install sentence-transformers    # Semantic vector search (~90 MB model)
pip install pytesseract              # OCR for screenshots
# Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki

pip install faster-whisper           # Local speech-to-text (~140 MB model)
pip install opencv-python-headless ultralytics numpy  # YOLO video/CCTV
```

### Optional Local LLM Brain (Ollama / LM Studio)

<details>
<summary><b>Ollama (recommended for local LLM)</b></summary>

```powershell
# Install Ollama, pull a model, then set in .env:
BRAIN_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:3b
```

</details>

<details>
<summary><b>LM Studio</b></summary>

```powershell
# Start local server on port 1234, then set in .env:
BRAIN_PROVIDER=lmstudio
```

</details>

> No LLM configured? Brain Chat uses `local_semantic` automatically — grounded rule-based answers, always available, zero dependencies.

---

## Demo Flow

A complete demo walkthrough is in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). Quick version:

```
1.  Open http://localhost:3000 — observe the Cognitive Core Orb (green/yellow)
2.  ◈ Ask Eidolon   — type "Who are you?" → Gemini reasoning paragraph
3.  ◈ Ask Eidolon   — type "What am I working on?" → memory-grounded answer
4.  ⌕ Search        — type any keyword → hybrid semantic + keyword results
5.  ◫ PDF Brain     — upload a PDF → ask "What is the main topic?"
6.  ◎ Voice Memory  — upload audio → local Whisper transcription → searchable
7.  ⬡ Vision / CCTV — start webcam → person detection → events in Timeline
8.  ◎ World Model   — live entity state from camera events
9.  ⬡ Agent         — click "Summarize Today" or "Open VSCode"
10. ◈ Profile tab   — Cognitive Profile with Gemini summary + domain bars
11. ◷ Trends tab    — 14-day activity chart + domain trend arrows
12. ◈ Replay        — pick a session → replay memories frame by frame
13. ◉ Soul          — behavioral patterns, workflow rhythm, project memory
14. ◎ Graph         — temporal memory relationships
```

---

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Frontend** | Next.js 16, React 19, TypeScript 5 | Single-page OS interface |
| **Backend** | Python 3.12, FastAPI 0.110 | REST API, 23 route modules |
| **Storage** | JSON flat files (pathlib) | Zero-dependency persistence |
| **Search** | sentence-transformers + BM25 | Hybrid keyword + vector search |
| **OCR** | Tesseract + pytesseract | Screenshot text extraction |
| **Vision** | YOLOv8 nano (ultralytics) | Object detection, 80 classes |
| **CV** | OpenCV (headless) | Frame sampling, motion detection |
| **Voice** | faster-whisper (base) | Local speech-to-text, CPU |
| **PDF** | PyMuPDF (fitz) | Text extraction, chunking |
| **Cloud AI (opt)** | Google Gemini 2.0 Flash | Synthesis, reasoning, profile |
| **LLM (opt)** | Ollama / LM Studio | Local conversational brain |
| **Intelligence** | python stdlib (Counter, defaultdict) | Clustering, trends, insights |
| **Concurrency** | Python threading | Daemon workers per camera/video |
| **Packaging** | pip / npm | No Docker, no container runtime |

---

## Project Structure

```
eidolon-os/
├── apps/
│   ├── api/                           # FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py                # Entrypoint: python -m uvicorn app.main:app
│   │   │   ├── api/routes/            # 23 route modules
│   │   │   │   ├── brain.py           # /brain/status, /brain/chat, /brain/reset
│   │   │   │   └── intelligence.py    # /intelligence/profile|timeline|clusters|insights
│   │   │   ├── services/              # 36 service modules
│   │   │   │   ├── gemini_bridge_service.py    # Gemini SDK wrapper
│   │   │   │   ├── gemini_tool_registry.py     # Agentic tool declarations
│   │   │   │   ├── intelligence_service.py     # Profile/trends/clustering
│   │   │   │   └── ...
│   │   │   └── core/config.py         # All configuration constants
│   │   ├── .env                       # Local config (gitignored)
│   │   └── .env.example               # Template
│   └── web/                           # Next.js frontend
│       └── src/app/page.tsx           # Single-page React application (~5200 lines)
├── storage/                           # All user data (gitignored)
│   ├── memory-db/memories.json
│   ├── session-db/sessions.json
│   ├── screenshots/
│   ├── uploads/pdfs · audio · video
│   └── cameras/
├── docs/                              # Full documentation suite
├── scripts/start_all.ps1              # One-command launcher
├── .env.example                       # All configurable variables
└── README.md
```

---

## API Endpoints (v0.21.0)

Key new endpoints added in Phase 21:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/brain/status` | Orb state, provider, quota info |
| `POST` | `/brain/chat` | Memory-grounded Gemini chat |
| `POST` | `/brain/reset` | Re-probe brain provider |
| `GET` | `/intelligence/profile` | Gemini cognitive profile |
| `GET` | `/intelligence/timeline` | 14-day trend analysis |
| `GET` | `/intelligence/clusters` | Memory domain clusters |
| `GET` | `/intelligence/insights` | Proactive auto-insights |
| `POST` | `/chat/stream` | SSE streaming chat (Ask Eidolon) |
| `POST` | `/chat/query` | Non-streaming chat |
| `GET` | `/identity/profile` | Full identity: projects, goals, focus, Gemini summary |
| `GET` | `/identity/projects` | Active project list with confidence + status |
| `GET` | `/identity/next` | "What should I work on next?" suggestion |

Full API reference: http://127.0.0.1:8010/docs

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1–20 | Core OS — memory, search, vision, voice, video, soul, agent, brain | ✅ Shipped |
| 21 | Gemini Hybrid — cloud AI layer, profile intelligence, trends, reasoning | ✅ Shipped |
| 22 | Identity Engine — project detection, goal inference, "Who am I?", identity synthesis | ✅ Shipped |
| 23 | Submission Pack — README, architecture, demo script, judge walkthrough | ✅ Shipped |
| 24 | Demo Polish — judge UX, chips, walkthrough card, wording | ✅ Shipped |
| **25** | **Release Candidate** — RC banner, footer strip, About dialog, Quick Facts | ✅ **Shipped** |
| 24 | Smart Recall — context injection, idle nudges, daily digest email | 📋 Planned |
| 25 | Mobile Companion — React Native, quick voice capture | 📋 Planned |
| 26 | Knowledge Graph UI — visual node explorer, export GraphML | 📋 Planned |
| 27+ | LAN sync · Plugin system · Voice wake word · EIDOLON Cloud (opt-in) | 🔮 Future |

See [docs/ROADMAP.md](docs/ROADMAP.md) for full details.

---

## Known Limitations

| Limitation | Notes |
|------------|-------|
| **Windows primary** | Tested on Windows 11. Linux/macOS may work with minor path adjustments. |
| **Single-user** | Designed for personal use — no multi-user auth or ACL. |
| **Gemini free tier** | Free AI Studio keys have per-day request limits. The UI shows quota status and retries gracefully. |
| **Gemini context** | Memory text snippets (not files) are sent to Gemini. The full `GEMINI_ALLOW_SYSTEM_LOCKDOWN=true` option prevents any context being sent. |
| **No live stream preview** | Camera analysis is backend-only; no video feed in the browser. |
| **CPU-bound video** | YOLO on long videos is slow without a GPU. |
| **Flat-file storage** | `memories.json` is loaded on each request — suitable up to ~50 K memories. |
| **No mobile app** | Browser-only for now; Tauri shell planned for Phase 22. |

---

## Contributing

Contributions are welcome. Core principles:

- **Local-first always** — no feature may *require* a cloud service, API key, or paid dependency
- **Graceful fallback** — every optional feature must degrade cleanly when its dependency is absent
- **No fake claims** — heuristic or estimated results must be labeled explicitly
- **Privacy by default** — no telemetry, analytics, or outbound calls without explicit opt-in

```powershell
git checkout -b feature/your-feature

# TypeScript check
cd apps/web && npx tsc --noEmit

# Python syntax check
cd apps/api && python -m py_compile app/services/your_service.py

# Submit a pull request
```

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Complete demo walkthrough — Google AI First Challenge flow |
| [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) | Step-by-step Windows installation guide |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and fixes |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full system architecture |
| [docs/PHASES.md](docs/PHASES.md) | Phase-by-phase build log |
| [docs/FEATURE_MAP.md](docs/FEATURE_MAP.md) | All API endpoints by phase |
| [docs/SYSTEM_FLOW.md](docs/SYSTEM_FLOW.md) | Data pipeline diagrams |
| [docs/PRIVACY.md](docs/PRIVACY.md) | Privacy policy (local-first) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Near-term and long-term plans |

---

## License

```
MIT License — Copyright (c) 2026 EIDOLON OS Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
```

---

<div align="center">

**Built local. Runs offline. Thinks with Gemini.**

*EIDOLON OS v0.25.0 RC — All 25 Phases Complete · Google AI First Challenge 2026*

</div>
