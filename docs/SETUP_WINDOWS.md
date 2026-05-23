# EIDOLON OS — Windows Setup Guide

Step-by-step setup on Windows 10/11. Tested on Windows 11 Home.

---

## Prerequisites

| Requirement        | Version       | Download                                              |
|--------------------|---------------|-------------------------------------------------------|
| Python             | 3.12.x        | https://www.python.org/downloads/                     |
| Node.js            | 18+ (LTS)     | https://nodejs.org/                                   |
| Git                | Any           | https://git-scm.com/                                  |

> Python 3.11 may work but 3.12 is tested. Node 20 LTS is recommended.

---

## Step 1 — Clone the repository

```powershell
git clone <your-repo-url> eidolon-os
cd eidolon-os
```

---

## Step 2 — Create Python virtual environment

```powershell
py -3.12 -m venv .venv-312
.venv-312\Scripts\Activate.ps1
```

If PowerShell blocks script execution:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## Step 3 — Install Python dependencies

```powershell
cd apps\api
pip install --upgrade pip
pip install -r requirements.txt
cd ..\..
```

---

## Step 4 — Install Node.js dependencies

```powershell
cd apps\web
npm install
cd ..\..
```

---

## Step 5 — Create .env file

```powershell
Copy-Item .env.example .env
```

Edit `.env` if you want to enable optional features (Ollama, LM Studio).
The default `.env` works with zero changes for local-only operation.

---

## Step 6 — Start the services

### Option A — Automated (recommended)

```powershell
.\scripts\start_all.ps1
```

This opens two PowerShell windows: one for the API, one for the frontend.

### Option B — Manual

**Terminal 1 (API):**
```powershell
.venv-312\Scripts\Activate.ps1
cd apps\api
uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

**Terminal 2 (Frontend):**
```powershell
cd apps\web
npm run dev
```

---

## Step 7 — Open the app

Open your browser and go to: **http://localhost:3000**

API documentation is at: **http://127.0.0.1:8010/docs**

---

## Optional: Install AI features

These are entirely optional. The app works without them.

### Semantic search (sentence-transformers)
```powershell
pip install sentence-transformers
```
Restart the API. First search will download the model (~90 MB, one time).

### Voice transcription (faster-whisper)
```powershell
pip install faster-whisper
```
Restart the API. First audio upload will download the Whisper base model (~140 MB).

### Video object detection (YOLO)
```powershell
pip install ultralytics
```
Restart the API. First video analysis will download YOLO nano (~6 MB).

### PDF text extraction (PyMuPDF)
```powershell
pip install pymupdf
```

### OCR for screenshots (Tesseract)
1. Download Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default path (`C:\Program Files\Tesseract-OCR\`)
3. Add to PATH or set `TESSERACT_CMD` in `.env`
4. Install pytesseract: `pip install pytesseract`

### Local LLM brain (Ollama)
1. Download Ollama from: https://ollama.com/download
2. After install: `ollama pull qwen2.5:3b`
3. Set `BRAIN_PROVIDER=ollama` in `.env`
4. Restart the API

### Local LLM brain (LM Studio)
1. Download LM Studio from: https://lmstudio.ai/
2. Load any GGUF model, start local server on port 1234
3. Set `BRAIN_PROVIDER=lmstudio` in `.env`
4. Restart the API

---

## Stopping the services

```powershell
.\scripts\stop_all.ps1
```

Or close the PowerShell windows manually.

---

## Common issues

See `docs/TROUBLESHOOTING.md` for solutions to common problems.

---

## Storage locations

All data is stored in `storage/` at the project root:

```
storage/
  memory-db/       ← memories.json
  session-db/      ← sessions.json
  screenshots/     ← screenshot images
  uploads/         ← uploaded files
  videos/          ← video files + thumbnails
  cameras/         ← camera registry
  exports/         ← export archives
```

To reset all data: delete the `storage/` directory and restart the API.
