# EIDOLON OS — Troubleshooting

Common issues and fixes for Windows setup.

---

## API won't start

### "ModuleNotFoundError: No module named 'app'"

**Cause:** PYTHONPATH not set.
**Fix:** Run uvicorn from inside `apps/api/`:
```powershell
cd apps\api
uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

### "Address already in use" on port 8010

**Fix:**
```powershell
.\scripts\stop_all.ps1
```
Or manually kill the process:
```powershell
netstat -ano | Select-String ":8010"
# Note the PID, then:
Stop-Process -Id <PID> -Force
```

### "python: command not found"

**Fix:** Use `py` (Windows launcher) or the full venv path:
```powershell
.venv-312\Scripts\python.exe -m uvicorn main:app --port 8010
```

---

## Frontend won't start

### "next: command not found" or "npm not found"

**Fix:** Install Node.js from https://nodejs.org/ then:
```powershell
cd apps\web
npm install
npm run dev
```

### Port 3000 already in use

**Fix:**
```powershell
netstat -ano | Select-String ":3000"
Stop-Process -Id <PID> -Force
```

---

## Features showing as unavailable

### "OCR: pytesseract installed but tesseract binary not found"

**Fix:** Install Tesseract-OCR:
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default path
3. Set in `.env`: `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`
4. Restart API

### "Voice: faster-whisper not installed"

**Fix:**
```powershell
pip install faster-whisper
```

### "Video: OpenCV not installed"

**Fix:**
```powershell
pip install opencv-python-headless ultralytics numpy
```

### "Search: keyword-only (install sentence-transformers for semantic search)"

**Fix:**
```powershell
pip install sentence-transformers
```
The first search after install will take a moment to download the model (~90 MB).

### "PDF: PyMuPDF not installed"

**Fix:**
```powershell
pip install pymupdf
```

---

## Camera / CCTV issues

### Camera won't start: "OpenCV not installed"

**Fix:** `pip install opencv-python-headless`

### "No camera found at index 0"

**Cause:** Webcam not detected or already in use.
**Fix:**
- Try index 1 or 2
- Close other apps using the camera (Teams, OBS, etc.)
- Check Device Manager for camera driver

### RTSP camera not connecting

**Fix:**
- Verify the RTSP URL is correct
- Ensure your firewall allows the camera IP
- Test with: `ffplay rtsp://your-camera-url`

---

## Brain / LLM issues

### "Brain: local_semantic" but BRAIN_PROVIDER=ollama in .env

**Cause:** Ollama is not running.
**Fix:**
1. Start Ollama: search "Ollama" in Start menu
2. Ensure model is downloaded: `ollama list`
3. If not: `ollama pull qwen2.5:3b`
4. Click "↺ Status" in the Brain Chat panel to re-probe

### LM Studio fallback to local_semantic

**Cause:** LM Studio server is not running or wrong port.
**Fix:**
1. Open LM Studio → Local Server → Start Server
2. Ensure port is 1234
3. Load a model before starting the server
4. Click "↺ Status" in the Brain Chat panel to re-probe

---

## Memory / Storage issues

### "Memory: store ready (empty)" but I've captured things before

**Cause:** `storage/memory-db/memories.json` may have been moved or deleted.
**Fix:** Check if the file exists:
```powershell
Test-Path storage\memory-db\memories.json
```
The storage directory must be at the project root (same level as `apps/`).

### API startup error: "FileNotFoundError" on storage path

**Fix:** The API creates storage dirs automatically on startup. Ensure you're running
from inside `apps/api/` and the root `storage/` directory is writable.

### Large memory.json causing slow startup

**Cause:** Thousands of memories, embedding backfill running.
**Fix:** The backfill runs in a background thread and does not block startup.
If it's very slow, you can disable sentence-transformers temporarily:
```powershell
pip uninstall sentence-transformers
```
And reinstall when needed.

---

## Windows-specific issues

### "Execution of scripts is disabled" (PowerShell)

**Fix:**
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### UnicodeDecodeError in Python on Windows

**Cause:** Default Windows encoding is cp1252, not UTF-8.
**Fix:** Already handled in config. If you see this in custom scripts, add:
```python
open(file, encoding='utf-8')
```

### Port conflicts after sleep/hibernate

**Fix:** Run `.\scripts\stop_all.ps1` then `.\scripts\start_all.ps1`.

---

## Getting more help

- API docs: http://127.0.0.1:8010/docs
- Check the API startup log for `✓` / warning messages per module
- Check `docs/SETUP_WINDOWS.md` for initial setup steps
- Open an issue at the project repository
