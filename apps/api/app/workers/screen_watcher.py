"""
Screen watcher — captures screenshots on an interval and stores them as memories.

Lifecycle:
    run_screen_watcher(interval_seconds)  → starts a daemon thread
    stop_screen_watcher()                 → signals the thread to stop cleanly
    is_running()                          → True while the thread is alive
"""

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.models.memory import MemoryItem
from app.services.embedding_service import embedding_service
from app.services.memory_store import memory_store
from app.services.ocr_service import extract_text_from_image
from app.services.screenshot_service import capture_screen
from app.services.window_service import get_active_window_info
from app.utils.ids import create_memory_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_thread: threading.Thread | None = None


def _ingest(path: Path) -> None:
    now = utc_now_iso()
    hms = datetime.now(timezone.utc).strftime("%H:%M:%S")
    memory_id = create_memory_id()

    ocr = extract_text_from_image(path)
    win = get_active_window_info()

    app_name     = win.get("app_name")
    window_title = win.get("window_title")
    exe_name     = win.get("exe_name")

    # Phase 11 — enhanced vision intelligence (fast heuristic, non-fatal)
    try:
        from app.services.vision_intelligence_service import analyze_screenshot_enhanced
        vision = analyze_screenshot_enhanced(ocr["text"], app_name, path, window_title)
    except Exception:
        try:
            from app.services.vision_service import analyze_screenshot
            vision = analyze_screenshot(ocr["text"], app_name, path)
        except Exception:
            vision = {}

    # Use smart_title when available, fall back to app + time
    smart = vision.get("smart_title", "")
    if smart and smart not in ("Screen Capture",):
        title = smart
    elif app_name:
        title = f"{app_name} - {hms}"
    else:
        title = f"Screen Capture - {hms}"

    # Build tags: app + scene + workflow + visual_tags
    tag_set: list[str] = []
    if app_name:
        tag_set.append(app_name)
    if vision.get("scene_type", "unknown") not in ("unknown",):
        tag_set.append(vision["scene_type"])
    if vision.get("workflow_type", "other") not in ("other",):
        tag_set.append(vision["workflow_type"])
    for vt in vision.get("visual_tags", []):
        if vt not in tag_set:
            tag_set.append(vt)
    tags = tag_set[:8]

    item = MemoryItem(
        id=memory_id,
        type="screenshot",
        title=title,
        text=ocr["text"],
        file_path=str(path),
        source="screen_capture",
        tags=tags,
        metadata={
            "ocr_engine":     ocr["engine"],
            "ocr_available":  ocr["available"],
            "ocr_confidence": ocr.get("confidence", -1.0),
            "app_name":       app_name,
            "window_title":   window_title,
            "exe_name":       exe_name,
            # Vision intelligence (Phase 11)
            "scene_type":     vision.get("scene_type", "unknown"),
            "workflow_type":  vision.get("workflow_type", "other"),
            "ui_layout":      vision.get("ui_layout", "unknown"),
            "visual_tags":    vision.get("visual_tags", []),
            "dominant_app":   vision.get("dominant_app", app_name or "unknown"),
            "confidence":     vision.get("confidence", 0.3),
            "active_tools":   vision.get("active_tools", []),
            "probable_task":  vision.get("probable_task", ""),
        },
        created_at=now,
        updated_at=now,
    )

    item_dict = item.model_dump()
    embedding = embedding_service.embed_for_storage(item_dict["title"], ocr["text"])
    if embedding is not None:
        item_dict["embedding"] = embedding

    memory_store.add(item_dict)
    logger.info(
        "Ingested screenshot %s  app=%s  embedding=%s",
        memory_id, app_name or "unknown", embedding is not None,
    )


_MAX_CONSECUTIVE_ERRORS = 5   # after this many failures, back off to 60 s
_BACKOFF_SLEEP          = 60  # seconds to sleep when backing off


def _loop(interval: int) -> None:
    logger.info("Screen watcher started (interval=%ds)", interval)
    consecutive_errors = 0

    while not _stop_event.is_set():
        try:
            path = capture_screen()
            _ingest(path)
            consecutive_errors = 0          # reset on success
        except Exception as exc:
            consecutive_errors += 1
            if consecutive_errors <= _MAX_CONSECUTIVE_ERRORS:
                logger.error(
                    "Screen capture cycle failed (%d/%d): %s",
                    consecutive_errors, _MAX_CONSECUTIVE_ERRORS, exc,
                )
            elif consecutive_errors == _MAX_CONSECUTIVE_ERRORS + 1:
                logger.error(
                    "Screen capture has failed %d times in a row — "
                    "backing off to %ds intervals. Last error: %s",
                    consecutive_errors, _BACKOFF_SLEEP, exc,
                )

        sleep_time = _BACKOFF_SLEEP if consecutive_errors > _MAX_CONSECUTIVE_ERRORS else interval
        _stop_event.wait(timeout=sleep_time)
    logger.info("Screen watcher stopped")


def run_screen_watcher(interval_seconds: int = 10) -> bool:
    """
    Start the watcher thread.
    Returns False (without starting) if already running.
    """
    global _thread

    if _thread and _thread.is_alive():
        return False

    _stop_event.clear()
    _thread = threading.Thread(
        target=_loop,
        args=(interval_seconds,),
        name="screen-watcher",
        daemon=True,  # auto-dies when the main process exits
    )
    _thread.start()
    return True


def stop_screen_watcher() -> bool:
    """
    Signal the watcher to stop and wait up to 5 s for it to finish.
    Returns False if it wasn't running.
    """
    global _thread

    if not _thread or not _thread.is_alive():
        return False

    _stop_event.set()
    _thread.join(timeout=5)
    return True


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()
