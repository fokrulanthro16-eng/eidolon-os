import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Root resolution
# This file lives at: apps/api/app/core/config.py
# parents[0] = apps/api/app/core
# parents[1] = apps/api/app
# parents[2] = apps/api
# parents[3] = apps
# parents[4] = eidolon-os  ← ROOT_DIR
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
ROOT_DIR: Path = _THIS_FILE.parents[4]

# ---------------------------------------------------------------------------
# Load .env if present (simple key=value, no dependency on python-dotenv)
# ---------------------------------------------------------------------------
_ENV_FILE = _THIS_FILE.parents[2] / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Project identity
# ---------------------------------------------------------------------------
PROJECT_NAME: str = "EIDOLON OS"
API_VERSION: str = "1.0.0"
PHASE: str = "Phase 20 — Demo Launch Ready"
LOCAL_FIRST: bool = True
ACTIVE_MODULES: list[str] = [
    "NeuroVision",          # screen capture + OCR
    "OmniMemory",           # JSON memory store
    "SemanticEngine",       # sentence-transformers hybrid search
    "LocalBrain",           # rule-based + optional Ollama
    "WindowIntelligence",   # active window detection
    "ReplayEngine",         # chronological session replay
    "PDFBrain",             # PDF ingestion + text extraction
    "PDFChat",              # PDF chunk retrieval + rule-based Q&A
    "VisionIntelligence",   # Phase 11: app fingerprinting + workflow detection
    "WorkflowEngine",       # Phase 11: workflow period aggregation
    "VoiceMemory",          # audio ingestion + Whisper transcription
    "DigitalSoul",          # behavioural profiling from local metadata
    "AutoSuggestions",      # grounded autonomous suggestions
    "VideoIntelligence",    # YOLO nano object detection + CCTV monitoring
    "PredictionLayer",      # live camera trajectory prediction
    "TemporalGraph",        # memory relationship graph by time/topic/session
    "AgentMode",            # Phase 12: local-only action registry
    "ReplayEngine2",        # Phase 13: AI memory replay by day/topic/modality/session
    "NeuralSearch",         # Phase 15: cross-modal neural search across all modalities
    "MultiCamera",          # Phase 16: named multi-camera registry + isolated workers
    "WorldModel",           # Phase 17: heuristic world-state from camera events
    "BrainRouter",          # Phase 18: optional local LLM adapter (Ollama / LM Studio)
]

# ---------------------------------------------------------------------------
# Ollama (optional — disabled by default)
# Set OLLAMA_ENABLED=true in .env to activate local LLM answers.
# ---------------------------------------------------------------------------
OLLAMA_ENABLED: bool = os.environ.get("OLLAMA_ENABLED", "false").lower() == "true"
OLLAMA_BASE_URL: str = os.environ.get(
    "OLLAMA_BASE_URL",
    os.environ.get("OLLAMA_URL", "http://localhost:11434"),
)
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

# Phase 18 — Brain Router
BRAIN_PROVIDER: str    = os.environ.get("BRAIN_PROVIDER", "local_semantic")
LMSTUDIO_BASE_URL: str = os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LMSTUDIO_MODEL: str    = os.environ.get("LMSTUDIO_MODEL", "local-model")

# ---------------------------------------------------------------------------
# Storage paths — all absolute, all Windows-safe via pathlib
# ---------------------------------------------------------------------------
STORAGE_DIR: Path = ROOT_DIR / "storage"
UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
PDF_UPLOADS_DIR: Path   = UPLOADS_DIR / "pdfs"
AUDIO_UPLOADS_DIR: Path = UPLOADS_DIR / "audio"
VIDEOS_DIR: Path        = STORAGE_DIR / "videos"
VIDEO_THUMBS_DIR: Path  = VIDEOS_DIR / "thumbnails"
SCREENSHOTS_DIR: Path   = STORAGE_DIR / "screenshots"
MEMORY_DB_DIR: Path = STORAGE_DIR / "memory-db"
MEMORY_DB_FILE: Path = MEMORY_DB_DIR / "memories.json"
SESSION_DB_DIR: Path = STORAGE_DIR / "session-db"
SESSION_DB_FILE: Path = SESSION_DB_DIR / "sessions.json"
VIDEO_DB_DIR: Path   = STORAGE_DIR / "video-db"
VIDEO_INDEX_FILE: Path = VIDEO_DB_DIR / "video_index.json"

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
ALLOWED_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
ALLOWED_VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm", ".m4v",
})
MAX_UPLOAD_MB: int = 20
MAX_UPLOAD_BYTES: int = MAX_UPLOAD_MB * 1024 * 1024
MAX_PDF_MB: int   = 50
MAX_PDF_BYTES: int = MAX_PDF_MB * 1024 * 1024
MAX_AUDIO_MB: int  = 200
MAX_AUDIO_BYTES: int = MAX_AUDIO_MB * 1024 * 1024
MAX_VIDEO_MB: int  = 2048
MAX_VIDEO_BYTES: int = MAX_VIDEO_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
