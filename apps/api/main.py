import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    agent, brain, camera, cameras, chat, digital_soul, export, graph, health,
    memory, neural_search, pdf, profile, replay_v2, sessions, suggestions,
    summary, system, video, vision, voice, world_model,
)
from app.core.config import (
    ACTIVE_MODULES,
    API_VERSION,
    CORS_ORIGINS,
    PHASE,
    PROJECT_NAME,
    SCREENSHOTS_DIR,
    UPLOADS_DIR,
    VIDEO_THUMBS_DIR,
)
from app.services.embedding_service import embedding_service
from app.services.memory_store import memory_store
from app.services.ocr_service import _TESSERACT_CMD
from app.services.pdf_service import pymupdf_available
from app.services.storage_service import ensure_storage_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("eidolon")

app = FastAPI(
    title=PROJECT_NAME,
    version=API_VERSION,
    description=f"{PROJECT_NAME} — {PHASE} API",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(system.router)
app.include_router(memory.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(export.router)
app.include_router(summary.router)
app.include_router(pdf.router)
app.include_router(profile.router)
app.include_router(suggestions.router)
app.include_router(video.router)
app.include_router(vision.router)
app.include_router(camera.router)
app.include_router(voice.router)
app.include_router(graph.router)
app.include_router(agent.router)
app.include_router(replay_v2.router)
app.include_router(digital_soul.router)
app.include_router(neural_search.router)
app.include_router(cameras.router)
app.include_router(world_model.router)
app.include_router(brain.router)

# Serve uploaded images and screenshots so the frontend can display them
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")
VIDEO_THUMBS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/video-thumbs", StaticFiles(directory=str(VIDEO_THUMBS_DIR)), name="video-thumbs")


@app.on_event("startup")
async def startup() -> None:
    ensure_storage_dirs()
    logger.info("━━━ %s  %s  [%s] ━━━", PROJECT_NAME, API_VERSION, PHASE)
    logger.info("Modules: %s", ", ".join(ACTIVE_MODULES))
    logger.info("Docs:    http://127.0.0.1:8010/docs")

    # --- Startup diagnostics ---
    # OCR status
    try:
        import pytesseract  # noqa: F401
        if _TESSERACT_CMD:
            logger.info("OCR:     tesseract ✓  (%s)", _TESSERACT_CMD)
        else:
            logger.info("OCR:     pytesseract installed but tesseract binary not found — fallback mode")
    except ImportError:
        logger.info("OCR:     pytesseract not installed — image text search disabled")

    # Semantic embeddings status
    if embedding_service.is_available():
        logger.info("Search:  sentence-transformers ✓  (hybrid keyword+semantic)")
    else:
        logger.info("Search:  keyword-only (install sentence-transformers for semantic search)")

    # PDF extraction status
    if pymupdf_available():
        import fitz
        logger.info("PDF:     PyMuPDF ✓  (v%s)", fitz.version[0])
    else:
        logger.info("PDF:     PyMuPDF not installed — run: pip install pymupdf")

    # Voice transcription status
    from app.services.voice_service import is_available as voice_available
    if voice_available():
        logger.info("Voice:   faster-whisper ✓  (base model / CPU)")
    else:
        logger.info("Voice:   faster-whisper not installed — run: pip install faster-whisper")

    # Vision intelligence (always available via heuristics)
    logger.info("Vision:  Phase 11 enhanced intelligence — app fingerprinting + workflow detection")

    # Video intelligence status
    from app.services.video_service import is_available as video_available
    cv_ok, yolo_ok = video_available()
    if cv_ok and yolo_ok:
        logger.info("Video:   OpenCV ✓  YOLO nano ✓  (full video intelligence active)")
    elif cv_ok:
        logger.info("Video:   OpenCV ✓  ultralytics missing — motion-only mode (pip install ultralytics)")
    else:
        logger.info("Video:   OpenCV not installed — run: pip install opencv-python-headless ultralytics numpy")

    # World model
    logger.info("World:   Phase 17 world model active (heuristic scene analysis)")

    # Brain router
    from app.core.config import BRAIN_PROVIDER
    logger.info("Brain:   Phase 18 router active — provider=%s", BRAIN_PROVIDER)

    # Memory graph
    logger.info("Graph:   temporal memory graph active (time/session/topic/app/workflow edges)")

    # Brain mode status
    try:
        from app.services.llm.local_brain import brain
        logger.info("Brain:   %s", brain.mode.value)
    except Exception:
        logger.info("Brain:   LOCAL_SEMANTIC (rule-based)")

    # Memory store stats
    try:
        count = len(memory_store.list())
        logger.info("Memory:  %d item(s) loaded from store", count)
    except Exception:
        logger.info("Memory:  store ready (empty)")

    # Backfill embeddings for existing items in the background
    def _backfill():
        embedding_service.backfill_embeddings(memory_store)

    threading.Thread(target=_backfill, name="embedding-backfill", daemon=True).start()


@app.get("/", tags=["root"])
async def root():
    return {
        "name": PROJECT_NAME,
        "phase": PHASE,
        "modules": ACTIVE_MODULES,
        "status": "online",
    }
