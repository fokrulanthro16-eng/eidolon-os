"""
Live Camera / CCTV endpoints.

POST /vision/camera/start   — start live camera capture in background thread
POST /vision/camera/stop    — stop live camera capture gracefully
GET  /vision/camera/status  — get current camera state (non-destructive)

All endpoints return the same CameraStatus shape:
{
    running:          bool,
    camera_available: bool | None,   # None = not yet probed
    detection_mode:   str,           # "yolo" | "motion_only" | "unavailable" | "unknown"
    last_event_time:  str | None,    # ISO-8601 of most recent stored event
    event_count:      int,           # total events stored this session
    error:            str | None,    # honest error message if something failed
}
"""

import logging

from fastapi import APIRouter, Query

from app.services.camera_service import get_predictions, get_status, start_camera, stop_camera

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision/camera", tags=["camera"])


@router.post("/start", summary="Start live camera capture")
async def camera_start(
    camera_index: int = Query(
        default=0,
        ge=0,
        le=9,
        description="OpenCV camera device index (0 = default webcam)",
    )
):
    """
    Start the live camera worker thread.

    Returns immediately with current status. If OpenCV is unavailable, the
    response will contain an honest error and camera_available=false — the
    backend never crashes.

    Only one camera thread runs at a time; calling start while already running
    is a no-op and returns the current status.
    """
    status = start_camera(camera_index=camera_index)
    return {"success": True, **status}


@router.post("/stop", summary="Stop live camera capture")
async def camera_stop():
    """
    Stop the live camera worker thread gracefully (waits up to 3 s).
    Safe to call when the camera is already stopped.
    """
    status = stop_camera()
    return {"success": True, **status}


@router.get("/status", summary="Get current camera state")
async def camera_status():
    """
    Return the current camera state without starting or stopping anything.
    Use this to poll status after calling /start.
    """
    return get_status()


@router.get("/predictions/active", summary="Get active object predictions")
async def camera_predictions():
    """
    Return live prediction data for all tracked objects.
    Each item includes track_id, label, direction, speed, predicted_x/y,
    prediction_events, and confidence.

    Returns an empty list when camera is stopped or YOLO is unavailable.
    Predictions are heuristic estimates — not guaranteed to be accurate.
    """
    return {"predictions": get_predictions()}
