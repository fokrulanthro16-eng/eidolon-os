"""
Multi-Camera Intelligence Service — Phase 16.

Manages a registry of named camera sources:
  - Webcam by index (0, 1, 2 …)
  - RTSP stream URL (rtsp://…)
  - Video file path (for replay / testing)

Each camera runs in its own daemon thread with isolated state.
Registry is persisted to storage/cameras/camera_registry.json.

Safety rules:
  - User must manually start each camera
  - No camera auto-starts at boot
  - No cloud streaming
  - All processing local-only
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _registry_path() -> Path:
    from app.core.config import STORAGE_DIR
    p = STORAGE_DIR / "cameras"
    p.mkdir(parents=True, exist_ok=True)
    return p / "camera_registry.json"


# ---------------------------------------------------------------------------
# Per-camera constants (shared with camera_service)
# ---------------------------------------------------------------------------

MOTION_THRESHOLD  = 0.015
EVENT_COOLDOWN    = 3.0
SAMPLE_INTERVAL   = 1.0
THUMB_W, THUMB_H  = 320, 180


# ---------------------------------------------------------------------------
# Registry + runtime state
# ---------------------------------------------------------------------------

_REGISTRY_LOCK = threading.Lock()
# camera_id → {"config": dict, "state": dict, "lock": Lock, "stop": Event, "thread": Thread|None}
_CAMERAS: dict[str, dict[str, Any]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load_registry() -> None:
    """Load persisted camera configs into _CAMERAS (without starting threads)."""
    path = _registry_path()
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for cfg in data.get("cameras", []):
            cid = cfg.get("camera_id")
            if cid and cid not in _CAMERAS:
                _CAMERAS[cid] = {
                    "config": {**cfg, "enabled": False},
                    "state": _empty_state(),
                    "lock":  threading.Lock(),
                    "stop":  threading.Event(),
                    "thread": None,
                }
    except Exception as exc:
        logger.warning("multi_camera: registry load failed: %s", exc)


def _save_registry() -> None:
    """Persist camera configs to disk."""
    path = _registry_path()
    configs = [cam["config"] for cam in _CAMERAS.values()]
    try:
        tmp = path.with_suffix(".tmp.json")
        tmp.write_text(json.dumps({"cameras": configs}, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.warning("multi_camera: registry save failed: %s", exc)


def _empty_state() -> dict:
    return {
        "running":          False,
        "camera_available": None,
        "detection_mode":   "unknown",
        "last_event_time":  None,
        "event_count":      0,
        "error":            None,
    }


# Load persisted cameras at module import
try:
    _load_registry()
except Exception:
    pass


# ---------------------------------------------------------------------------
# Camera worker
# ---------------------------------------------------------------------------

def _camera_worker(camera_id: str) -> None:
    cam = _CAMERAS.get(camera_id)
    if not cam:
        return

    cfg   = cam["config"]
    state = cam["state"]
    lock  = cam["lock"]
    stop  = cam["stop"]
    stop.clear()

    source_type = cfg.get("source_type", "webcam")
    source      = cfg.get("source", "0")
    name        = cfg.get("name", camera_id)

    # Resolve source
    if source_type == "webcam":
        try:
            cam_index = int(source)
        except (ValueError, TypeError):
            cam_index = 0
        cap_source: Any = cam_index
    else:
        cap_source = source  # RTSP URL or file path

    # Probe OpenCV
    try:
        import cv2
    except ImportError:
        with lock:
            state.update({
                "running":          False,
                "camera_available": False,
                "detection_mode":   "unavailable",
                "error":            "OpenCV not installed. Run: pip install opencv-python-headless",
            })
        return

    # Probe YOLO
    yolo_model  = None
    detect_mode = "motion_only"
    try:
        from ultralytics import YOLO
        yolo_model  = YOLO("yolov8n.pt")
        detect_mode = "yolo"
    except Exception:
        pass

    with lock:
        state["detection_mode"] = detect_mode

    # Open capture
    cap = cv2.VideoCapture(cap_source)
    if not cap.isOpened():
        with lock:
            state.update({
                "running":          False,
                "camera_available": False,
                "error":            f"Cannot open camera source '{source}'.",
            })
        return

    with lock:
        state.update({"camera_available": True, "error": None})

    logger.info("multi_camera[%s]: started — mode=%s  source=%s", camera_id, detect_mode, source)

    prev_gray      = None
    last_event_ts  = 0.0
    last_sample_ts = time.time()
    frame_idx      = 0

    try:
        import numpy as np
        while not stop.is_set():
            ret, frame = cap.read()
            if not ret:
                with lock:
                    state["error"]            = "Camera read failed."
                    state["camera_available"] = False
                break

            now_ts = time.time()
            if (now_ts - last_sample_ts) < SAMPLE_INTERVAL:
                time.sleep(0.05)
                continue
            last_sample_ts = now_ts
            frame_idx += 1

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            has_motion = False
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                has_motion = (np.count_nonzero(diff > 25) / gray.size) > MOTION_THRESHOLD
            prev_gray = gray

            if not has_motion or (now_ts - last_event_ts) < EVENT_COOLDOWN:
                continue

            last_event_ts = now_ts
            event_id  = _uid()
            thumb_url = _save_thumb(frame, camera_id, event_id)

            detected: list[str] = []
            event_type  = "motion_detected"
            description = f"Motion detected on {name}"

            if yolo_model is not None:
                try:
                    from app.services.video_service import CCTV_CLASSES, COCO_NAMES, CONF_THRESHOLD
                    try:
                        results = yolo_model.track(frame, classes=CCTV_CLASSES, conf=CONF_THRESHOLD,
                                                   persist=True, verbose=False)
                    except Exception:
                        results = yolo_model(frame, classes=CCTV_CLASSES, conf=CONF_THRESHOLD, verbose=False)
                    for r in results:
                        if r.boxes is None:
                            continue
                        for box in r.boxes:
                            lbl = COCO_NAMES.get(int(box.cls[0]), "object")
                            if lbl not in detected:
                                detected.append(lbl)
                    if detected:
                        if "person" in detected:
                            event_type  = "person_detected"
                            description = f"Person detected on {name}"
                        else:
                            event_type  = "object_detected"
                            description = f"Detected on {name}: {', '.join(detected)}"
                except Exception as exc:
                    logger.debug("multi_camera YOLO error: %s", exc)

            if not detected:
                detected = ["motion"]

            _store_camera_event(camera_id, name, event_type, description, detected, thumb_url)

            with lock:
                state["last_event_time"] = _utc_now_iso()
                state["event_count"] = state.get("event_count", 0) + 1

    except Exception as exc:
        logger.exception("multi_camera[%s] crashed: %s", camera_id, exc)
        with lock:
            state["error"] = str(exc)
    finally:
        cap.release()
        with lock:
            state["running"] = False
        logger.info("multi_camera[%s]: stopped", camera_id)


def _save_thumb(frame: Any, camera_id: str, event_id: str) -> str | None:
    try:
        import cv2
        from app.core.config import SCREENSHOTS_DIR
        cam_dir = SCREENSHOTS_DIR / f"camera-{camera_id}"
        cam_dir.mkdir(parents=True, exist_ok=True)
        name = f"cam_{event_id}.jpg"
        thumb = cv2.resize(frame, (THUMB_W, THUMB_H))
        cv2.imwrite(str(cam_dir / name), thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return f"/screenshots/camera-{camera_id}/{name}"
    except Exception:
        return None


def _store_camera_event(camera_id: str, camera_name: str, event_type: str,
                         description: str, labels: list[str], thumb_url: str | None) -> None:
    try:
        from app.models.memory import MemoryItem
        from app.services.embedding_service import embedding_service
        from app.services.memory_store import memory_store
        from app.utils.ids import create_memory_id

        now    = _utc_now_iso()
        mem_id = create_memory_id()
        tags   = sorted({"video", "cctv", "camera", f"camera-{camera_id}",
                          event_type.replace("_", "-")} | set(labels))
        item = MemoryItem(
            id=mem_id,
            type="video",
            title=f"{camera_name}: {description}",
            text=description,
            file_path=None,
            source="live_camera",
            tags=tags,
            metadata={
                "event_type":       event_type,
                "labels":           labels,
                "thumbnail_url":    thumb_url,
                "camera_id":        camera_id,
                "camera_name":      camera_name,
                "camera_source":    "live_camera",
                "analysis_status":  "done",
                "detected_objects": labels,
            },
            created_at=now,
            updated_at=now,
        )
        d = item.model_dump()
        emb = embedding_service.embed_for_storage(item.title, description)
        if emb is not None:
            d["embedding"] = emb
        memory_store.add(d)
    except Exception as exc:
        logger.debug("multi_camera store failed: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_camera(
    name: str,
    source_type: str = "webcam",
    source: str = "0",
    enabled: bool = True,
) -> dict:
    if source_type not in ("webcam", "rtsp", "file"):
        return {"success": False, "message": f"Invalid source_type '{source_type}'."}
    camera_id = _uid()
    cfg = {
        "camera_id":    camera_id,
        "name":         name,
        "source_type":  source_type,
        "source":       source,
        "enabled":      enabled,
        "detection_mode": "unknown",
        "created_at":   _utc_now_iso(),
    }
    with _REGISTRY_LOCK:
        _CAMERAS[camera_id] = {
            "config": cfg,
            "state":  _empty_state(),
            "lock":   threading.Lock(),
            "stop":   threading.Event(),
            "thread": None,
        }
        _save_registry()
    logger.info("multi_camera: added %s (%s=%s)", name, source_type, source)
    return {"success": True, "camera_id": camera_id, "config": cfg}


def remove_camera(camera_id: str) -> dict:
    with _REGISTRY_LOCK:
        cam = _CAMERAS.get(camera_id)
        if not cam:
            return {"success": False, "message": f"Camera '{camera_id}' not found."}
        # Stop if running
        cam["stop"].set()
        t = cam.get("thread")
        if t and t.is_alive():
            t.join(timeout=3.0)
        del _CAMERAS[camera_id]
        _save_registry()
    return {"success": True, "camera_id": camera_id}


def list_cameras() -> list[dict]:
    with _REGISTRY_LOCK:
        result = []
        for cid, cam in _CAMERAS.items():
            with cam["lock"]:
                result.append({**cam["config"], **cam["state"]})
        return result


def start_camera_by_id(camera_id: str) -> dict:
    with _REGISTRY_LOCK:
        cam = _CAMERAS.get(camera_id)
        if not cam:
            return {"success": False, "message": f"Camera '{camera_id}' not found."}
        with cam["lock"]:
            if cam["state"].get("running"):
                return {"success": True, "message": "Already running.", **cam["state"]}
            cam["state"]["running"] = True
            cam["state"]["error"]   = None

    t = threading.Thread(
        target=_camera_worker,
        args=(camera_id,),
        name=f"cam-{camera_id}",
        daemon=True,
    )
    with _REGISTRY_LOCK:
        _CAMERAS[camera_id]["thread"] = t
    t.start()
    return {"success": True, "camera_id": camera_id, "message": "Camera started."}


def stop_camera_by_id(camera_id: str) -> dict:
    with _REGISTRY_LOCK:
        cam = _CAMERAS.get(camera_id)
    if not cam:
        return {"success": False, "message": f"Camera '{camera_id}' not found."}
    cam["stop"].set()
    t = cam.get("thread")
    if t and t.is_alive():
        t.join(timeout=3.0)
    with cam["lock"]:
        cam["state"]["running"] = False
        cam["thread"] = None
    return {"success": True, "camera_id": camera_id, "message": "Camera stopped."}


def get_camera_status(camera_id: str) -> dict:
    cam = _CAMERAS.get(camera_id)
    if not cam:
        return {"success": False, "message": f"Camera '{camera_id}' not found."}
    with cam["lock"]:
        return {**cam["config"], **cam["state"], "success": True}


def get_all_events(limit: int = 100) -> list[dict]:
    """Return recent camera events from all cameras."""
    try:
        from app.services.memory_store import memory_store
        mems = [
            m for m in memory_store.list()
            if m.get("type") == "video" and m.get("source") == "live_camera"
        ]
        mems.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return mems[:limit]
    except Exception:
        return []
