"""
Multi-Camera Intelligence endpoints — Phase 16.

GET    /cameras/list                    — list all registered cameras
POST   /cameras/add                     — register a new camera source
DELETE /cameras/{camera_id}             — remove a camera
POST   /cameras/{camera_id}/start       — start a camera worker
POST   /cameras/{camera_id}/stop        — stop a camera worker
GET    /cameras/{camera_id}/status      — get runtime state for one camera
GET    /cameras/events                  — recent events from all cameras
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cameras", tags=["multi-camera"])


class AddCameraRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    source_type: str = Field(default="webcam", description="webcam | rtsp | file")
    source: str = Field(default="0", description="Webcam index, RTSP URL, or file path")


# NOTE: /cameras/events and /cameras/list must be defined BEFORE
# /{camera_id}/* routes to avoid FastAPI matching "events"/"list" as camera IDs.

@router.get("/list", summary="List all registered cameras")
async def list_cameras():
    """Return config + runtime state for every registered camera."""
    from app.services.multi_camera_service import list_cameras as _list
    return {"cameras": _list()}


@router.get("/events", summary="Recent events from all cameras")
async def camera_events(limit: int = 100):
    """Return the most recent camera events across all named cameras."""
    from app.services.multi_camera_service import get_all_events
    return {"events": get_all_events(limit), "limit": limit}


@router.post("/add", summary="Register a new camera source")
async def add_camera(req: AddCameraRequest):
    """
    Add a named camera to the registry.

    source_type options:
      - webcam  → source = device index (e.g. "0", "1")
      - rtsp    → source = full RTSP URL  (e.g. "rtsp://192.168.1.10:554/stream")
      - file    → source = local video path (for replay / testing)
    """
    from app.services.multi_camera_service import add_camera as _add
    return _add(req.name, req.source_type, req.source)


@router.post("/{camera_id}/start", summary="Start a camera worker")
async def start_camera(camera_id: str):
    """Start the background worker for the given camera."""
    from app.services.multi_camera_service import start_camera_by_id
    return start_camera_by_id(camera_id)


@router.post("/{camera_id}/stop", summary="Stop a camera worker")
async def stop_camera(camera_id: str):
    """Stop the background worker for the given camera."""
    from app.services.multi_camera_service import stop_camera_by_id
    return stop_camera_by_id(camera_id)


@router.get("/{camera_id}/status", summary="Get runtime status for one camera")
async def camera_status(camera_id: str):
    """Return config + runtime state for a single camera."""
    from app.services.multi_camera_service import get_camera_status
    return get_camera_status(camera_id)


@router.delete("/{camera_id}", summary="Remove a camera from the registry")
async def delete_camera(camera_id: str):
    """Stop the worker (if running) and remove the camera from the registry."""
    from app.services.multi_camera_service import remove_camera
    return remove_camera(camera_id)
