# EIDOLON OS — Backend API

Phase 1 MVP: NeuroVision + OmniMemory  
Local-first memory engine. No database required. No AI models required to start.

---

## Setup

```powershell
cd C:\Users\WALTON\eidolon-os\apps\api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Run

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

---

## URLs

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000 | Root identity |
| http://127.0.0.1:8000/health | Health check |
| http://127.0.0.1:8000/system/info | System info + storage paths |
| http://127.0.0.1:8000/docs | Swagger UI (interactive) |
| http://127.0.0.1:8000/redoc | ReDoc documentation |

---

## API Reference

### `GET /` — Root identity
### `GET /health` — Health check → `{"status":"ok","service":"eidolon-api"}`
### `GET /system/info` — Project name, version, phase, all storage paths
### `POST /memory/ingest-image` — Upload image → OCR → memory item
### `GET /memory/list` — All items, insertion order
### `GET /memory/timeline` — All items, newest first
### `POST /memory/search` — Scored text search → `{"query":"..."}`
### `DELETE /memory/{memory_id}` — Delete item + file

---

## PowerShell Examples

```powershell
# Health
Invoke-RestMethod http://127.0.0.1:8000/health

# System info
Invoke-RestMethod http://127.0.0.1:8000/system/info

# Upload an image (use curl.exe on Windows PowerShell 5.1)
curl.exe -X POST http://127.0.0.1:8000/memory/ingest-image `
  -F "file=@C:\path\to\screenshot.png" `
  -F "source_app=VSCode" `
  -F "window_title=My Window"

# List all memory
Invoke-RestMethod http://127.0.0.1:8000/memory/list

# Timeline (newest first)
Invoke-RestMethod http://127.0.0.1:8000/memory/timeline

# Search
Invoke-RestMethod http://127.0.0.1:8000/memory/search `
  -Method Post `
  -Body '{"query": "dashboard"}' `
  -ContentType "application/json"

# Delete
Invoke-RestMethod http://127.0.0.1:8000/memory/mem_abc12345 -Method Delete
```

---

## Storage Layout

```
storage/
├── uploads/          # Saved images: {mem_id}_{sanitized_name}.ext
├── screenshots/      # Future: auto-captured screenshots
└── memory-db/
    └── memories.json # Atomic JSON database (auto-created)
```

---

## Optional Upgrades

### Real OCR
```powershell
# Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
pip install pytesseract
# Restart API — activates automatically
```

### Semantic search
```powershell
pip install sentence-transformers
# Restart API — model downloads on first use (~80 MB)
```

---

## Next Step: Connect Next.js Frontend

```typescript
// apps/web — set API base URL
const API = "http://127.0.0.1:8000"
```

CORS is pre-configured for `localhost:3000`.

---

## Legacy stack docs

| Layer | Tech | Status |
|---|---|---|
| API | FastAPI + Uvicorn | Required |
| Storage | Local JSON files | Required |
| OCR | pytesseract + Tesseract | Optional |
| Search | sentence-transformers | Optional |

Runs fully without OCR or semantic search installed.
Both degrade gracefully with placeholder behavior.

---

## Quick Start

### 1. Navigate to the API directory

```powershell
cd C:\Users\WALTON\eidolon-os\apps\api
```

### 2. Install dependencies

```powershell
pip install fastapi uvicorn[standard] python-multipart pillow pydantic pydantic-settings aiofiles
```

### 3. Run the API

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open docs

```
http://localhost:8000/docs
```

---

## API Reference

### `GET /`
System identity. Confirms the API is alive.

### `GET /health`
Returns capability status: OCR, search mode, storage.

### `POST /memory/ingest-image`
Upload an image. Runs OCR, stores memory item, returns ID + extracted text.

**Form fields:**
- `file` (required) — image file
- `source_app` (optional) — e.g. `"VSCode"`
- `window_title` (optional) — e.g. `"main.py - VSCode"`

### `GET /memory/list`
Returns all memory items, newest first.
Query params: `limit` (default 50), `offset` (default 0).

### `POST /memory/search`
Search memory by query string.

```json
{
  "query": "python neural network",
  "top_k": 10,
  "source_type": null
}
```

### `GET /memory/{id}`
Fetch a single memory item by ID.

### `DELETE /memory/{id}`
Delete a memory item.

---

## Test Commands

### curl (PowerShell)

```powershell
# Health check
curl http://localhost:8000/health

# Ingest an image
curl -X POST http://localhost:8000/memory/ingest-image `
  -F "file=@C:\path\to\image.png" `
  -F "source_app=VSCode"

# List all memory
curl http://localhost:8000/memory/list

# Search
curl -X POST http://localhost:8000/memory/search `
  -H "Content-Type: application/json" `
  -d '{"query": "python code", "top_k": 5}'
```

---

## Enable OCR

```powershell
# 1. Install Tesseract binary
# Download: https://github.com/UB-Mannheim/tesseract/wiki
# Add C:\Program Files\Tesseract-OCR\ to PATH

# 2. Install Python binding
pip install pytesseract

# 3. Restart API — OCR activates automatically
```

## Enable Semantic Search

```powershell
pip install sentence-transformers

# Add to .env:
EMBEDDINGS_ENABLED=True

# Restart API — first run downloads all-MiniLM-L6-v2 (~80MB)
```

---

## Storage Layout

```
storage/
├── uploads/     # raw image files: {memory_id}_{filename}
└── memory/      # JSON records: {memory_id}.json
```

Each `.json` file is a complete, self-contained MemoryItem.
Human-readable, inspectable, no database required.

---

## Next Steps

1. Install Tesseract → real OCR
2. Install sentence-transformers → semantic search
3. Connect Next.js frontend at `apps/web`
4. Upgrade storage → PostgreSQL + pgvector (Phase 2)
