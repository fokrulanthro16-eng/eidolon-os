# EIDOLON OS — Privacy Policy

**Last updated:** 2026-05-23

EIDOLON OS is a **local-first** system. This document explains what data is collected,
where it is stored, and what never leaves your machine.

---

## What EIDOLON OS collects

EIDOLON OS captures data from your own machine at your explicit request:

| Data type        | Source                                      | Stored at                        |
|------------------|---------------------------------------------|----------------------------------|
| Screenshots      | Your screen (you initiate capture)          | `storage/screenshots/`           |
| OCR text         | Extracted from your screenshots             | `storage/memory-db/memories.json`|
| PDF text         | From PDFs you upload                        | `storage/memory-db/memories.json`|
| Voice transcripts| From audio files you upload                 | `storage/memory-db/memories.json`|
| Video events     | From video files / cameras you configure    | `storage/memory-db/memories.json`|
| Session metadata | Timestamps + window titles                  | `storage/session-db/sessions.json`|
| Camera frames    | Your configured cameras (not saved as video)| Memory store (events only)       |

---

## What EIDOLON OS does NOT do

- ❌ Does not send any data to the internet
- ❌ Does not connect to Anthropic, OpenAI, or any cloud AI service
- ❌ Does not require an account or login
- ❌ Does not install browser extensions or intercept network traffic
- ❌ Does not monitor other users, devices, or accounts
- ❌ Does not store continuous video (events only, configurable)
- ❌ Does not infer personal identity, biometrics, or health data

---

## Optional external connections

These are **disabled by default** and only activate if you explicitly configure them:

| Feature             | Activated by                    | Connects to                         |
|---------------------|---------------------------------|-------------------------------------|
| Ollama brain        | `BRAIN_PROVIDER=ollama` in .env | `http://localhost:11434` (local)    |
| LM Studio brain     | `BRAIN_PROVIDER=lmstudio`       | `http://127.0.0.1:1234` (local)    |
| RTSP camera stream  | You add a camera with RTSP URL  | Your local network only             |

All of these connect to **local services on your own machine or LAN only**.
None connect to the internet.

---

## Data storage

All data is stored in the `storage/` directory inside the project root:

```
storage/
  memory-db/       ← All memories (JSON)
  session-db/      ← Session index (JSON)
  screenshots/     ← Screenshot images
  uploads/         ← Uploaded PDFs, audio, video
  videos/          ← Processed videos + thumbnails
  cameras/         ← Camera registry
  exports/         ← Exported archives
```

You own all of this data. You can delete it at any time by removing the `storage/` directory.

---

## Third-party libraries

EIDOLON OS uses open-source libraries. None of them phone home:

- `FastAPI` — web framework (Python)
- `sentence-transformers` — local embeddings (no model download at runtime)
- `faster-whisper` — local speech-to-text (no cloud)
- `ultralytics` — YOLO nano object detection (local model file)
- `opencv-python-headless` — computer vision (local)
- `PyMuPDF` — PDF parsing (local)
- `Next.js` — frontend framework (local)

---

## Model files

If you install optional AI features, model files are downloaded once and stored locally:

| Model                    | Location                   | When downloaded         |
|--------------------------|----------------------------|-------------------------|
| YOLO nano (`yolov8n.pt`) | User cache dir             | First video analysis    |
| Whisper base             | User cache dir             | First audio transcription |
| sentence-transformers    | User cache dir             | First semantic search   |

Models are never uploaded. They are only read locally.

---

## Your rights

Since all data is stored locally on your machine:

- **Access:** Read `storage/memory-db/memories.json` directly
- **Export:** Use `POST /export` or the Export button in the UI
- **Delete:** Remove any item via `DELETE /memory/{id}` or the UI trash icon
- **Full wipe:** Delete the `storage/` directory

No data removal request needs to be submitted to anyone — you control the data entirely.

---

## Contact

EIDOLON OS is an open-source project. Report issues at the project repository.
There is no company collecting your data.
