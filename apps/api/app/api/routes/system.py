from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import (
    ACTIVE_MODULES,
    API_VERSION,
    LOCAL_FIRST,
    MEMORY_DB_DIR,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    PHASE,
    PROJECT_NAME,
    SCREENSHOTS_DIR,
    UPLOADS_DIR,
)
from app.services.llm import get_brain
from app.workers.screen_watcher import is_running, run_screen_watcher, stop_screen_watcher

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
async def system_info():
    brain = get_brain()
    return {
        "name":           PROJECT_NAME,
        "version":        API_VERSION,
        "phase":          PHASE,
        "local_first":    LOCAL_FIRST,
        "active_modules": ACTIVE_MODULES,
        "storage": {
            "uploads":    str(UPLOADS_DIR),
            "screenshots": str(SCREENSHOTS_DIR),
            "memory_db":  str(MEMORY_DB_DIR),
        },
        "screen_watcher": {"running": is_running()},
        "brain":          brain.status(),
    }


@router.get("/ollama")
async def ollama_status():
    """
    Live Ollama connectivity check.

    Returns current status plus actionable setup instructions when offline.
    """
    brain = get_brain()
    bs    = brain.status()
    alive = bs.get("llm_active", False)
    model = bs.get("ollama_model", OLLAMA_MODEL)

    setup_instructions = None
    if not alive:
        setup_instructions = {
            "step_1": "Download and install Ollama: https://ollama.com/download",
            "step_2": "Start the Ollama server: ollama serve",
            "step_3": f"Pull the model: ollama pull {model}",
            "step_4": "Restart the EIDOLON API — it will detect Ollama automatically",
            "env_config": {
                "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
                "OLLAMA_MODEL":    model,
            },
        }

    return {
        "online":           alive,
        "url":              OLLAMA_BASE_URL,
        "configured_model": model,
        "available_models": bs.get("available_models", []),
        "mode":             bs.get("mode"),
        "setup":            setup_instructions,
    }


class WatcherStartRequest(BaseModel):
    interval_seconds: int = Field(default=10, ge=1, le=3600)


@router.post("/start-screen-watch")
async def start_screen_watch(body: WatcherStartRequest = WatcherStartRequest()):
    if not run_screen_watcher(interval_seconds=body.interval_seconds):
        raise HTTPException(status_code=409, detail="Screen watcher is already running")
    return {"success": True, "interval_seconds": body.interval_seconds}


@router.post("/stop-screen-watch")
async def stop_screen_watch():
    if not stop_screen_watcher():
        raise HTTPException(status_code=409, detail="Screen watcher is not running")
    return {"success": True}
