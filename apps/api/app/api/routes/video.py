"""
Video Intelligence endpoints.

POST /video/upload              — upload a video, start background analysis
GET  /video/list                — list all videos with status + summary
GET  /video/{video_id}          — metadata + first 20 events
GET  /video/{video_id}/events   — paginated events, optional type filter
GET  /video/{video_id}/status   — {status, progress, event_count}
DELETE /video/{video_id}        — delete video file + events
GET  /video/search?q=           — keyword search across all video events
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from app.services.video_store import video_store
from app.services.video_service import is_available, start_analysis
from app.services.storage_service import save_video_file, delete_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["video"])


# ---------------------------------------------------------------------------
# Upload + trigger analysis
# ---------------------------------------------------------------------------

@router.post("/upload", summary="Upload a video file and begin AI analysis")
async def upload_video(file: UploadFile = File(...)):
    """
    Accepts mp4, avi, mov, mkv, wmv, webm, m4v up to 2 GB.
    Returns immediately with video_id; analysis runs in background.
    """
    # Create placeholder record first to get a video_id
    record = video_store.add_video(
        filename="",
        file_path="",
        file_size=0,
        original_name=file.filename or "video",
    )
    video_id = record["id"]

    try:
        saved_path = await save_video_file(file, video_id)
    except HTTPException:
        video_store.delete_video(video_id)
        raise

    file_size = saved_path.stat().st_size
    video_store.update_video(
        video_id,
        filename=saved_path.name,
        file_path=str(saved_path),
        file_size=file_size,
        original_name=file.filename or saved_path.name,
    )

    cv_ok, yolo_ok = is_available()
    if not cv_ok:
        video_store.update_video(
            video_id,
            status="error",
            error="opencv-python-headless not installed. Run: pip install opencv-python-headless ultralytics numpy",
        )
        return {
            "video_id":   video_id,
            "status":     "error",
            "message":    "OpenCV not installed — cannot analyse video.",
            "install":    "pip install opencv-python-headless ultralytics numpy",
        }

    start_analysis(video_id, str(saved_path), video_store)

    return {
        "video_id":    video_id,
        "status":      "analyzing",
        "file_size":   file_size,
        "original_name": file.filename,
        "yolo_active": yolo_ok,
        "message":     "Analysis started. Poll /video/{id}/status for progress.",
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/list", summary="List all uploaded videos")
def list_videos():
    videos = video_store.list_videos()
    return {"count": len(videos), "videos": videos}


# ---------------------------------------------------------------------------
# Search  (must be before /{video_id} to avoid routing conflict)
# ---------------------------------------------------------------------------

@router.get("/search", summary="Search events across all videos")
def search_events(q: str = Query(..., min_length=1, description="Keyword query")):
    results = video_store.search_events(q)
    return {"query": q, "count": len(results), "results": results}


# ---------------------------------------------------------------------------
# Single video detail
# ---------------------------------------------------------------------------

@router.get("/{video_id}", summary="Get video metadata + first 20 events")
def get_video(video_id: str):
    rec = video_store.get_video(video_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Video not found")
    events = video_store.get_events(video_id, limit=20)
    return {**rec, "events": events}


# ---------------------------------------------------------------------------
# Events (paginated, filterable)
# ---------------------------------------------------------------------------

@router.get("/{video_id}/events", summary="Get events for a video")
def get_video_events(
    video_id: str,
    event_type: str | None = Query(None, description="Filter by event type"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    if video_store.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    events = video_store.get_events(video_id, event_type=event_type, offset=offset, limit=limit)
    return {"video_id": video_id, "count": len(events), "offset": offset, "events": events}


# ---------------------------------------------------------------------------
# Status polling
# ---------------------------------------------------------------------------

@router.get("/{video_id}/status", summary="Poll analysis status + progress")
def get_video_status(video_id: str):
    rec = video_store.get_video(video_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return {
        "video_id":    video_id,
        "status":      rec["status"],
        "progress":    rec["progress"],
        "event_count": rec["event_count"],
        "error":       rec.get("error"),
    }


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{video_id}", summary="Delete a video and its events")
def delete_video(video_id: str):
    rec = video_store.get_video(video_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete the raw video file
    file_path = rec.get("file_path")
    if file_path:
        delete_file(file_path)

    # Delete thumbnail if present
    thumb = rec.get("thumbnail_path")
    if thumb:
        # thumb is a URL like /video-thumbs/filename.jpg
        from app.core.config import VIDEO_THUMBS_DIR
        thumb_file = VIDEO_THUMBS_DIR / Path(thumb).name
        delete_file(thumb_file)

    video_store.delete_video(video_id)
    return {"deleted": True, "video_id": video_id}
