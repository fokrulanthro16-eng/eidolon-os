<div align="center">

```
███████╗██╗██████╗  ██████╗ ██╗      ██████╗ ███╗   ██╗      ██████╗ ███████╗
██╔════╝██║██╔══██╗██╔═══██╗██║     ██╔═══██╗████╗  ██║     ██╔═══██╗██╔════╝
█████╗  ██║██║  ██║██║   ██║██║     ██║   ██║██╔██╗ ██║     ██║   ██║███████╗
██╔══╝  ██║██║  ██║██║   ██║██║     ██║   ██║██║╚██╗██║     ██║   ██║╚════██║
███████╗██║██████╔╝╚██████╔╝███████╗╚██████╔╝██║ ╚████║     ╚██████╔╝███████║
╚══════╝╚═╝╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝      ╚═════╝ ╚══════╝
```

### Your computer's second brain. No cloud. No subscription. No compromise.

<br/>

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2011-0078D6?style=flat-square&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Local First](https://img.shields.io/badge/local--first-zero%20cloud-10D984?style=flat-square)](#privacy)
[![No API Key](https://img.shields.io/badge/API%20key-none%20required-10D984?style=flat-square)](#installation)
[![Phase](https://img.shields.io/badge/phase-20%20%E2%80%94%20launch%20ready-8B5CF6?style=flat-square)](#roadmap)
[![License](https://img.shields.io/badge/license-MIT-F59E0B?style=flat-square)](LICENSE)

<br/>

**[Demo Script](docs/DEMO_SCRIPT.md) · [Architecture](docs/ARCHITECTURE.md) · [Privacy Policy](docs/PRIVACY.md) · [Roadmap](docs/ROADMAP.md) · [Setup Guide](docs/SETUP_WINDOWS.md)**

</div>

---

<br/>

> **EIDOLON OS** is an open-source, Windows-native AI cognitive system that captures everything you do on your computer — screenshots, documents, audio, video, camera feeds — and makes it all **searchable, replayable, and intelligently connected**. Zero cloud. Zero API keys. Zero surveillance. Everything lives on your machine.

<br/>

---

## Screenshots

<div align="center">

| Timeline & Search | Vision Intelligence | Agent Console |
|:-:|:-:|:-:|
| <img src="docs/assets/screenshot-timeline.png" alt="Timeline" width="280"/> | <img src="docs/assets/screenshot-vision.png" alt="Vision" width="280"/> | <img src="docs/assets/screenshot-agent.png" alt="Agent" width="280"/> |
| *Every memory, fully searchable* | *YOLO detection · World Model* | *Local actions · Brain Chat* |

| Replay Studio | Digital Soul | Memory Graph |
|:-:|:-:|:-:|
| <img src="docs/assets/screenshot-replay.png" alt="Replay" width="280"/> | <img src="docs/assets/screenshot-soul.png" alt="Soul" width="280"/> | <img src="docs/assets/screenshot-graph.png" alt="Graph" width="280"/> |
| *Replay any day, topic, or session* | *Behavioral intelligence from metadata* | *Temporal memory relationships* |

> 📸 Screenshots coming soon — run `.\scripts\start_all.ps1` and explore at `http://localhost:3000`

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
<tr><td><b>BrainRouter</b></td><td>18</td><td>Optional local LLM adapter · Ollama · LM Studio · local_semantic default</td><td>Ollama / LMStudio <em>(optional)</em></td><td>✅ Core</td></tr>
<tr><td><b>TemporalGraph</b></td><td>9+</td><td>Memory relationship graph · time / session / topic / app edges</td><td>—</td><td>✅ Core</td></tr>
<tr><td><b>PredictionLayer</b></td><td>10+</td><td>Live CCTV trajectory prediction · direction · speed · [Estimated]</td><td>opencv + ultralytics</td><td>✅ Core</td></tr>
<tr><td><b>Desktop Shell</b></td><td>19</td><td>Tauri / Electron native wrapper · system tray · auto-start</td><td>Rust toolchain</td><td>🗺 Planned</td></tr>
</tbody>
</table>

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                               EIDOLON OS                                     │
│                                                                              │
│   ┌─────────────────────────┐   HTTP/JSON   ┌──────────────────────────────┐│
│   │   Next.js 14  (: 3000)  │◄─────────────►│   FastAPI backend  (: 8010)  ││
│   │   React 18  TypeScript  │               │                              ││
│   │   Single-page app       │               │  ┌──────────┐  ┌──────────┐  ││
│   │                         │               │  │  Routes  │  │ Services │  ││
│   │  Tabs:                  │               │  │  21 mods │  │  22 mods │  ││
│   │   Timeline  Sessions    │               │  └────┬─────┘  └────┬─────┘  ││
│   │   Vision    Replay      │               │       └──────┬───────┘        ││
│   │   Soul      Graph       │               │              ▼                ││
│   │   Profile   Agent       │               │   ┌──────────────────────┐   ││
│   └─────────────────────────┘               │   │   Local Storage      │   ││
│                                             │   │   storage/           │   ││
│   ┌─────────────────────────┐               │   │   ├─ memory-db/      │   ││
│   │  Optional local LLMs    │               │   │   ├─ session-db/     │   ││
│   │                         │               │   │   ├─ screenshots/    │   ││
│   │  Ollama  ─── :11434     │◄──────────────┤   │   ├─ uploads/        │   ││
│   │  LM Studio ── :1234     │               │   │   ├─ videos/         │   ││
│   │  (both optional)        │               │   │   └─ cameras/        │   ││
│   └─────────────────────────┘               │   └──────────────────────┘   ││
│                                             └──────────────────────────────┘│
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Background Workers (daemon threads)                                 │  │
│   │  screen_watcher · camera_worker(s) · video_analyzer · embed_backfill │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘

        No internet. No database server. No message queue. No auth service.
                     Everything is a file on your local drive.
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
╠══════════════════════════════════════════════════════════════════╣
║  ❌  Never sends data to the internet                            ║
║  ❌  No cloud AI service (Anthropic, OpenAI, Google) used        ║
║  ❌  No telemetry, analytics, or crash reporting                 ║
║  ❌  No account, login, or subscription required                 ║
║  ❌  No continuous video recording (events only)                 ║
╚══════════════════════════════════════════════════════════════════╝
```

</div>

All data lives in `storage/` at the project root. You own it completely. See [docs/PRIVACY.md](docs/PRIVACY.md) for the full policy.

---

## Installation

### Prerequisites

| Requirement | Version | Download |
|-------------|---------|----------|
| Python | **3.12.x** | [python.org](https://www.python.org/downloads/) |
| Node.js | **18+ LTS** | [nodejs.org](https://nodejs.org/) |
| Git | any | [git-scm.com](https://git-scm.com/) |

### Backend Setup

```powershell
# 1. Clone the repository
git clone https://github.com/your-username/eidolon-os.git
cd eidolon-os

# 2. Create Python 3.12 virtual environment
py -3.12 -m venv .venv-312
.venv-312\Scripts\Activate.ps1

# 3. Install core dependencies
cd apps\api
pip install -r requirements.txt

# 4. Create your .env file
cd ..\..
Copy-Item .env.example .env
```

### Frontend Setup

```powershell
cd apps\web
npm install
```

### Launch

```powershell
# One-command launch (opens two PowerShell windows)
.\scripts\start_all.ps1
```

Or manually in two terminals:

```powershell
# Terminal 1 — API server
cd apps\api && uvicorn main:app --host 127.0.0.1 --port 8010 --reload

# Terminal 2 — Frontend
cd apps\web && npm run dev
```

| Service | URL |
|---------|-----|
| **Dashboard** | http://localhost:3000 |
| **API Docs (Swagger)** | http://127.0.0.1:8010/docs |
| **API Docs (ReDoc)** | http://127.0.0.1:8010/redoc |

> **Execution policy error?** Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

---

## Optional AI Features

Everything below is **opt-in**. EIDOLON OS runs fully without any of them.

### PDF, Search & OCR

```powershell
pip install pymupdf              # PDF text extraction (highly recommended)
pip install sentence-transformers # Semantic vector search (downloads ~90 MB model once)
pip install pytesseract           # OCR for screenshots (also needs Tesseract binary)
# Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki
```

### Voice Transcription

```powershell
pip install faster-whisper        # Local Whisper — downloads ~140 MB base model on first use
```

Upload any `.mp3 / .wav / .m4a / .ogg` file. Transcription runs fully offline on CPU.

### Video Intelligence & CCTV (YOLO)

```powershell
pip install opencv-python-headless ultralytics numpy
```

YOLO nano (`yolov8n.pt`, ~6 MB) is downloaded once on first video analysis. Runs on CPU — no GPU required. Detects persons, vehicles, bags, and 77 other object classes from uploaded video files and live webcam/RTSP streams.

### Optional Local LLM Brain

By default, Brain Chat uses `local_semantic` — a zero-dependency rule-based engine that always works and always answers from real memories.

To upgrade to a real conversational LLM:

<details>
<summary><b>Ollama (recommended)</b></summary>

```powershell
# 1. Install Ollama: https://ollama.com/download
# 2. Pull a small model
ollama pull qwen2.5:3b   # ~2 GB, runs well on 8 GB RAM

# 3. Enable in .env
BRAIN_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:3b
```

</details>

<details>
<summary><b>LM Studio</b></summary>

```powershell
# 1. Install LM Studio: https://lmstudio.ai/
# 2. Load any GGUF model and start the local server on port 1234

# 3. Enable in .env
BRAIN_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
```

</details>

> No Ollama or LM Studio? Brain Chat falls back to `local_semantic` automatically — no crash, no error.

---

## Demo Flow

A complete 13-step walkthrough is in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). Quick version:

```
1.  Open http://localhost:3000
2.  ◈ Timeline     — browse all captured memories, newest first
3.  ⌕ Search       — type "FastAPI" or any keyword for hybrid search results
4.  ◫ PDF Brain    — upload a PDF → ask "What is this document about?"
5.  ◎ Voice Memory — upload an audio file → Whisper transcription → searchable
6.  ◉ Video YOLO   — upload video → YOLO analysis → object detection events
7.  ⊕ Live Camera  — start webcam CCTV → motion + object detection → Timeline
8.  ◈ Multi-Cam   — add named cameras (webcam index / RTSP URL / video file)
9.  ◎ World Model  — see heuristic scene state from all active camera events
10. ◈ Replay       — pick a date → watch your entire day's activity in order
11. ◉ Digital Soul — behavioral patterns · workflow rhythm · project memory
12. ⬡ Agent        — click "Summarize Today", "Open VSCode", "Continue Last Session"
13. ◈ Brain Chat   — ask "What was I working on yesterday?" → grounded answer
```

---

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Frontend** | Next.js 14, React 18, TypeScript 5 | Single-page OS interface |
| **Backend** | Python 3.12, FastAPI 0.110 | REST API, 21 route modules |
| **Storage** | JSON flat files (pathlib) | Zero-dependency persistence |
| **Search** | sentence-transformers + BM25 | Hybrid keyword + vector search |
| **OCR** | Tesseract + pytesseract | Screenshot text extraction |
| **Vision** | YOLOv8 nano (ultralytics) | Object detection, 80 classes |
| **CV** | OpenCV (headless) | Frame sampling, motion detection |
| **Voice** | faster-whisper (base) | Local speech-to-text, CPU |
| **PDF** | PyMuPDF (fitz) | Text extraction, chunking |
| **LLM (opt)** | Ollama / LM Studio | Local conversational brain |
| **Concurrency** | Python threading | Daemon workers per camera/video |
| **Packaging** | pip / npm | No Docker, no container runtime |

---

## Project Structure

```
eidolon-os/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── main.py             # App entrypoint + startup diagnostics
│   │   └── app/
│   │       ├── api/routes/     # 21 route modules
│   │       ├── services/       # 22 service modules
│   │       ├── workers/        # screen_watcher daemon
│   │       └── core/config.py  # All configuration constants
│   └── web/                    # Next.js frontend
│       └── src/app/page.tsx    # Single-page React application
├── storage/                    # All user data (gitignored)
│   ├── memory-db/              # memories.json
│   ├── session-db/             # sessions.json
│   ├── screenshots/            # captured images
│   ├── uploads/                # pdfs / audio / video
│   └── cameras/                # camera registry
├── docs/                       # Full documentation suite
├── desktop/                    # Tauri / Electron plans
├── scripts/                    # start_all.ps1, stop_all.ps1
├── .env.example                # All configurable variables
└── README.md
```

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1–20 | Core OS — memory, search, vision, voice, video, soul, agent, brain | ✅ Shipped |
| **21** | **Tauri Desktop Shell** — system tray, hot-key capture, single EXE | 🔨 Next |
| 22 | Memory Timeline 2.0 — infinite scroll, heat-map navigation | 📋 Planned |
| 23 | Smart Recall — context injection, idle nudges, daily digest | 📋 Planned |
| 24 | Mobile Companion — React Native, quick voice capture | 📋 Planned |
| 25 | Knowledge Graph UI — visual node explorer, export GraphML | 📋 Planned |
| 26+ | LAN sync · Plugin system · Voice wake word · EIDOLON Cloud (opt-in) | 🔮 Future |

See [docs/ROADMAP.md](docs/ROADMAP.md) for full details.

---

## Known Limitations

| Limitation | Notes |
|------------|-------|
| **Windows primary** | Tested on Windows 11. Linux/macOS may work with minor path adjustments. |
| **Single-user** | Designed for personal use — no multi-user auth or ACL. |
| **No live stream preview** | Camera analysis is backend-only; no video feed shown in the browser. |
| **CPU-bound video** | YOLO analysis on long videos can be slow without a GPU. |
| **World Model is heuristic** | All predictions are labeled `[Estimated]` — not guaranteed accurate. |
| **Brain Chat without LLM** | `local_semantic` gives grounded rule-based answers, not free conversation. |
| **No mobile app** | Browser-only for now; Tauri shell planned for Phase 21. |
| **Flat-file storage** | `memories.json` is loaded into memory on each request — suitable up to ~50 K memories. |

---

## Contributing

Contributions are welcome. Please keep these principles in mind:

- **Local-first always** — no feature may require a cloud service, API key, or paid dependency
- **Graceful fallback** — every optional feature must degrade cleanly when its dependency is absent
- **No fake claims** — if a feature is heuristic or estimated, label it explicitly
- **Privacy by default** — no telemetry, analytics, or outbound calls may be added

```powershell
# Fork → clone → create a feature branch
git checkout -b feature/your-feature

# Make changes, then verify TypeScript
cd apps/web && npx tsc --noEmit

# Verify Python syntax
cd apps/api && python -m py_compile app/services/your_service.py

# Submit a pull request with a clear description of what changed and why
```

Issues and feature requests: open a GitHub Issue with a clear reproduction or specification.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) | Step-by-step Windows installation guide |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and their fixes |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | 13-step live demo walkthrough |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full system architecture |
| [docs/PHASES.md](docs/PHASES.md) | Phase-by-phase build log |
| [docs/FEATURE_MAP.md](docs/FEATURE_MAP.md) | All API endpoints by phase |
| [docs/SYSTEM_FLOW.md](docs/SYSTEM_FLOW.md) | Data pipeline diagrams |
| [docs/PRIVACY.md](docs/PRIVACY.md) | Privacy policy (local-first) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Near-term and long-term plans |
| [desktop/README.md](desktop/README.md) | Desktop shell plan (Tauri / Electron) |

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

**Built local. Runs offline. Stays private.**

*EIDOLON OS — Phase 20 · Demo Launch Ready*

</div>
