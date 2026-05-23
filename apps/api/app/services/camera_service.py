"""
Live Camera / CCTV Service — OpenCV frame capture + motion detection.

Dependencies (all optional):
    pip install opencv-python-headless ultralytics numpy

Architecture:
- Single background daemon thread manages the camera
- Thread-safe state via threading.Lock
- Motion detection via frame differencing (cv2.absdiff)
- Optional YOLO object detection if ultralytics installed
- Camera events stored as MemoryItems (type=video, source=live_camera)
- Thumbnails saved to storage/screenshots/camera-events/

Rules:
- Never crash if camera unavailable
- Never block backend startup
- Thread must stop safely
- Only one camera worker at a time
- If OpenCV missing, return clear unavailable status
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — protected by _LOCK
# ---------------------------------------------------------------------------

_LOCK = threading.Lock()
_stop_event = threading.Event()

_state: dict[str, Any] = {
    "running":          False,
    "camera_available": None,   # None = not probed yet
    "detection_mode":   "unknown",
    "last_event_time":  None,
    "event_count":      0,
    "error":            None,
    "thread":           None,
}

MOTION_THRESHOLD       = 0.015   # fraction of pixels changed
EVENT_COOLDOWN         = 3.0     # seconds between stored detection events
PREDICTION_COOLDOWN    = 10.0    # seconds between stored prediction events (per event type)
SAMPLE_INTERVAL        = 1.0     # sample 1 frame per second
THUMB_W, THUMB_H       = 320, 180

# Per-event-type timestamp of last stored prediction (guards against spam)
_pred_last_stored: dict[str, float] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())[:8]


def _save_camera_thumb(frame: Any, event_id: str) -> str | None:
    """Resize frame and save as JPEG thumbnail. Returns relative URL or None."""
    try:
        import cv2
        from app.core.config import SCREENSHOTS_DIR
        cam_dir = SCREENSHOTS_DIR / "camera-events"
        cam_dir.mkdir(parents=True, exist_ok=True)
        name = f"cam_{event_id}.jpg"
        thumb = cv2.resize(frame, (THUMB_W, THUMB_H))
        cv2.imwrite(str(cam_dir / name), thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return f"/screenshots/camera-events/{name}"
    except Exception as exc:
        logger.debug("camera thumb failed: %s", exc)
        return None


def _store_prediction_event(prediction: dict, thumbnail_url: str | None) -> None:
    """
    Persist a prediction event as a MemoryItem when prediction_events are present.
    Rate-limited per event type via _pred_last_stored.
    """
    pred_events = prediction.get("prediction_events", [])
    if not pred_events:
        return

    now_ts = time.time()
    for evt_type in pred_events:
        last = _pred_last_stored.get(evt_type, 0.0)
        if (now_ts - last) < PREDICTION_COOLDOWN:
            continue
        _pred_last_stored[evt_type] = now_ts

        label = prediction.get("label", "object")
        direction = prediction.get("direction", "")
        speed = prediction.get("speed", 0.0)
        confidence = prediction.get("confidence", 0.5)
        track_id = prediction.get("track_id", "?")

        description = (
            f"Prediction: {evt_type.replace('_', ' ')} — "
            f"{label} moving {direction} (speed {speed:.3f}, track {track_id})"
        )

        try:
            from app.models.memory import MemoryItem
            from app.services.embedding_service import embedding_service
            from app.services.memory_store import memory_store
            from app.utils.ids import create_memory_id

            now = _now_iso()
            mem_id = create_memory_id()
            tags = sorted({"video", "cctv", "camera", "prediction", label,
                           evt_type.replace("_", "-")})

            item = MemoryItem(
                id=mem_id,
                type="video",
                title=f"Prediction: {evt_type.replace('_', ' ')}",
                text=description,
                file_path=None,
                source="live_camera",
                tags=tags,
                metadata={
                    "event_type":        evt_type,
                    "prediction_type":   evt_type,
                    "labels":            [label],
                    "thumbnail_url":     thumbnail_url,
                    "analysis_engine":   _state.get("detection_mode", "unknown"),
                    "camera_source":     "live_camera",
                    "analysis_status":   "done",
                    "direction":         direction,
                    "speed":             speed,
                    "confidence":        confidence,
                    "current_position":  {
                        "x": prediction.get("current_x"),
                        "y": prediction.get("current_y"),
                    },
                    "predicted_position": {
                        "x": prediction.get("predicted_x"),
                        "y": prediction.get("predicted_y"),
                    },
                },
                created_at=now,
                updated_at=now,
            )
            item_dict = item.model_dump()
            emb = embedding_service.embed_for_storage(item.title, description)
            if emb is not None:
                item_dict["embedding"] = emb

            memory_store.add(item_dict)
            logger.info("prediction event: %s  track=%s  direction=%s", evt_type, track_id, direction)
        except Exception as exc:
            logger.debug("prediction event store failed: %s", exc)


def _store_event(
    event_type: str,
    description: str,
    labels: list[str],
    thumbnail_url: str | None,
) -> None:
    """
    Persist a camera detection as a MemoryItem.
    Uses deferred imports to avoid circular dependencies at module load time.
    """
    try:
        from app.models.memory import MemoryItem
        from app.services.embedding_service import embedding_service
        from app.services.memory_store import memory_store
        from app.utils.ids import create_memory_id

        now    = _now_iso()
        mem_id = create_memory_id()
        tags   = sorted({"video", "cctv", "camera", "live",
                          event_type.replace("_", "-")} | set(labels))

        item = MemoryItem(
            id=mem_id,
            type="video",
            title=f"Camera: {description}",
            text=description,
            file_path=None,
            source="live_camera",
            tags=tags,
            metadata={
                "event_type":        event_type,
                "labels":            labels,
                "thumbnail_url":     thumbnail_url,
                "analysis_engine":   _state.get("detection_mode", "unknown"),
                "camera_source":     "live_camera",
                "analysis_status":   "done",
                "detected_objects":  labels,
            },
            created_at=now,
            updated_at=now,
        )
        item_dict = item.model_dump()
        emb = embedding_service.embed_for_storage(item.title, description)
        if emb is not None:
            item_dict["embedding"] = emb

        memory_store.add(item_dict)

        with _LOCK:
            _state["last_event_time"] = now
            _state["event_count"]     = _state.get("event_count", 0) + 1

        logger.info("camera event: %s  labels=%s", event_type, labels)
    except Exception as exc:
        logger.debug("camera event store failed: %s", exc)


# ---------------------------------------------------------------------------
# Camera worker (runs in daemon thread)
# ---------------------------------------------------------------------------

def _camera_worker(camera_index: int) -> None:
    _stop_event.clear()

    # --- Probe OpenCV ---
    try:
        import cv2
    except ImportError:
        with _LOCK:
            _state.update({
                "running":          False,
                "camera_available": False,
                "detection_mode":   "unavailable",
                "error":            "OpenCV not installed. Run: pip install opencv-python-headless",
            })
        return

    # --- Probe YOLO ---
    yolo_model   = None
    detect_mode  = "motion_only"
    try:
        from ultralytics import YOLO
        yolo_model  = YOLO("yolov8n.pt")   # ~6 MB download on first run
        detect_mode = "yolo"
        logger.info("camera[%d]: YOLO nano loaded", camera_index)
    except Exception as exc:
        logger.info("camera[%d]: YOLO unavailable (%s) — motion-only mode", camera_index, exc)

    with _LOCK:
        _state["detection_mode"] = detect_mode

    # --- Open camera ---
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        with _LOCK:
            _state.update({
                "running":          False,
                "camera_available": False,
                "error":            f"Cannot open camera index {camera_index}. "
                                    "Check that a camera is connected and not in use.",
            })
        return

    with _LOCK:
        _state.update({"camera_available": True, "error": None})

    logger.info("camera[%d]: started — detection_mode=%s", camera_index, detect_mode)

    prev_gray      = None
    last_event_ts  = 0.0
    last_sample_ts = time.time()
    frame_idx      = 0

    from app.services.prediction_service import camera_tracker
    camera_tracker.reset()

    try:
        while not _stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                with _LOCK:
                    _state["error"]            = "Camera read failed — device may be disconnected."
                    _state["camera_available"] = False
                break

            now_ts = time.time()
            if (now_ts - last_sample_ts) < SAMPLE_INTERVAL:
                time.sleep(0.05)
                continue
            last_sample_ts = now_ts
            frame_idx += 1

            import numpy as np
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Motion check
            has_motion = False
            if prev_gray is not None:
                diff    = cv2.absdiff(prev_gray, gray)
                changed = np.count_nonzero(diff > 25)
                has_motion = (changed / gray.size) > MOTION_THRESHOLD
            prev_gray = gray

            if not has_motion or (now_ts - last_event_ts) < EVENT_COOLDOWN:
                # Still run predictions even if no new event to store
                if yolo_model is not None and has_motion:
                    _run_yolo_tracking(yolo_model, frame, frame_idx, now_ts, camera_tracker, thumb_url=None)
                camera_tracker.evict_stale(frame_idx)
                continue

            last_event_ts = now_ts
            event_id = _uid()
            thumb_url = _save_camera_thumb(frame, event_id)

            detected: list[str] = []
            event_type  = "motion_detected"
            description = "Motion detected by camera"

            if yolo_model is not None:
                try:
                    from app.services.video_service import (
                        CCTV_CLASSES, COCO_NAMES, CONF_THRESHOLD,
                    )
                    # Use .track() for persistent IDs when YOLO supports it
                    try:
                        results = yolo_model.track(
                            frame,
                            classes=CCTV_CLASSES,
                            conf=CONF_THRESHOLD,
                            persist=True,
                            verbose=False,
                        )
                    except Exception:
                        results = yolo_model(
                            frame,
                            classes=CCTV_CLASSES,
                            conf=CONF_THRESHOLD,
                            verbose=False,
                        )

                    for r in results:
                        if r.boxes is None:
                            continue
                        for box in r.boxes:
                            cls_id = int(box.cls[0])
                            lbl = COCO_NAMES.get(cls_id, "object")
                            if lbl not in detected:
                                detected.append(lbl)

                            # Feed prediction tracker
                            try:
                                x1, y1, x2, y2 = box.xyxyn[0].tolist()
                                cx = (x1 + x2) / 2
                                cy = (y1 + y2) / 2
                                area = (x2 - x1) * (y2 - y1)
                                tid = (
                                    f"yolo_{int(box.id[0])}"
                                    if box.id is not None
                                    else f"det_{cls_id}_{frame_idx}"
                                )
                                pred = camera_tracker.update(
                                    tid, cls_id, lbl, cx, cy, area, frame_idx, now_ts
                                )
                                if pred:
                                    _store_prediction_event(pred, thumb_url)
                            except Exception as pred_exc:
                                logger.debug("prediction update error: %s", pred_exc)

                    if detected:
                        if "person" in detected:
                            others = [l for l in detected if l != "person"]
                            event_type  = "person_detected"
                            description = (
                                f"Person detected by camera — also: {', '.join(others)}"
                                if others else "Person detected by camera"
                            )
                        else:
                            event_type  = "object_detected"
                            description = f"Detected by camera: {', '.join(detected)}"
                except Exception as exc:
                    logger.debug("camera YOLO error: %s", exc)

            if not detected:
                detected = ["motion"]

            camera_tracker.evict_stale(frame_idx)
            _store_event(event_type, description, detected, thumb_url)

    except Exception as exc:
        logger.exception("camera worker crashed: %s", exc)
        with _LOCK:
            _state["error"] = str(exc)
    finally:
        cap.release()
        camera_tracker.reset()
        with _LOCK:
            _state["running"] = False
        logger.info("camera[%d]: stopped", camera_index)


def _run_yolo_tracking(yolo_model: Any, frame: Any, frame_idx: int, now_ts: float, tracker: Any, thumb_url: str | None) -> None:
    """Run YOLO tracking on a frame and update the prediction tracker. Errors are swallowed."""
    try:
        from app.services.video_service import CCTV_CLASSES, COCO_NAMES, CONF_THRESHOLD
        try:
            results = yolo_model.track(frame, classes=CCTV_CLASSES, conf=CONF_THRESHOLD, persist=True, verbose=False)
        except Exception:
            results = yolo_model(frame, classes=CCTV_CLASSES, conf=CONF_THRESHOLD, verbose=False)
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                lbl = COCO_NAMES.get(cls_id, "object")
                x1, y1, x2, y2 = box.xyxyn[0].tolist()
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                area = (x2 - x1) * (y2 - y1)
                tid = (
                    f"yolo_{int(box.id[0])}"
                    if box.id is not None
                    else f"det_{cls_id}_{frame_idx}"
                )
                pred = tracker.update(tid, cls_id, lbl, cx, cy, area, frame_idx, now_ts)
                if pred:
                    _store_prediction_event(pred, thumb_url)
    except Exception as exc:
        logger.debug("_run_yolo_tracking error: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_camera(camera_index: int = 0) -> dict:
    """
    Start the camera worker thread.
    Returns immediately with current status.
    Safe to call if already running — returns status without starting a second thread.
    """
    with _LOCK:
        if _state["running"]:
            return _snapshot()

    # Probe OpenCV before spawning the thread
    try:
        import cv2  # noqa: F401
    except ImportError:
        with _LOCK:
            _state.update({
                "camera_available": False,
                "detection_mode":   "unavailable",
                "error":            "OpenCV not installed. Run: pip install opencv-python-headless",
            })
        return _snapshot()

    with _LOCK:
        _state["running"] = True
        _state["error"]   = None

    t = threading.Thread(
        target=_camera_worker,
        args=(camera_index,),
        name="camera-worker",
        daemon=True,
    )
    with _LOCK:
        _state["thread"] = t
    t.start()
    return _snapshot()


def stop_camera() -> dict:
    """Stop the camera worker thread gracefully (≤ 3 s join)."""
    _stop_event.set()
    with _LOCK:
        t = _state.get("thread")
    if t and t.is_alive():
        t.join(timeout=3.0)
    from app.services.prediction_service import camera_tracker
    camera_tracker.reset()
    with _LOCK:
        _state["running"] = False
        _state["thread"]  = None
    return _snapshot()


def get_status() -> dict:
    """Thread-safe snapshot of camera state."""
    return _snapshot()


def get_predictions() -> list[dict]:
    """Return active prediction items from the live camera tracker."""
    try:
        from app.services.prediction_service import camera_tracker
        return camera_tracker.get_active()
    except Exception:
        return []


def _snapshot() -> dict:
    with _LOCK:
        return {
            "running":          _state.get("running", False),
            "camera_available": _state.get("camera_available"),
            "detection_mode":   _state.get("detection_mode", "unknown"),
            "last_event_time":  _state.get("last_event_time"),
            "event_count":      _state.get("event_count", 0),
            "error":            _state.get("error"),
        }
