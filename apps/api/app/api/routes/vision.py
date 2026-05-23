"""
Vision Intelligence endpoint.

POST /vision/ingest-video   — upload video, run YOLO/motion analysis,
                              create a searchable MemoryItem of type "video"

The MemoryItem is created immediately with status "analyzing".
The background thread updates it with full metadata once analysis completes.
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.memory import MemoryItem
from app.services.embedding_service import embedding_service
from app.services.memory_store import memory_store
from app.services.storage_service import save_video_file
from app.services.video_service import is_available, start_analysis
from app.services.video_store import video_store
from app.utils.ids import create_memory_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vision", tags=["vision"])


@router.post(
    "/ingest-video",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a video for AI analysis and memory indexing",
)
async def ingest_video(file: UploadFile = File(...)):
    """
    Upload a video file (.mp4 .avi .mov .mkv .wmv .webm .m4v).

    Pipeline:
        validate → save → create MemoryItem (type=video) → start background
        analysis (YOLO nano / motion detection) → update MemoryItem on completion.

    The endpoint returns immediately. Poll GET /video/{video_id}/status for progress.
    Requires opencv-python-headless for analysis; degrades to metadata-only otherwise.
    Requires ultralytics for YOLO object detection; falls back to motion detection only.
    """
    memory_id = create_memory_id()
    now = utc_now_iso()
    original_name = file.filename or "video.mp4"

    # Create a video_store record first (for analysis tracking)
    video_record = video_store.add_video(
        filename="",
        file_path="",
        file_size=0,
        original_name=original_name,
    )
    video_id = video_record["id"]

    # Save the file
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
        original_name=original_name,
    )

    cv_ok, yolo_ok = is_available()
    analysis_engine = "yolo_nano" if yolo_ok else ("motion_only" if cv_ok else "unavailable")
    fallback_mode = not cv_ok

    placeholder_text = (
        f"Video file: {original_name}. Analysis in progress."
        if cv_ok
        else f"Video file: {original_name}. Install opencv-python-headless to enable analysis."
    )

    item = MemoryItem(
        id=memory_id,
        type="video",
        title=original_name,
        text=placeholder_text,
        file_path=str(saved_path),
        source="video_upload",
        tags=["video", "cctv", "analyzing"],
        metadata={
            "original_filename": original_name,
            "file_size":         file_size,
            "video_id":          video_id,
            "analysis_engine":   analysis_engine,
            "fallback_mode":     fallback_mode,
            "analysis_status":   "analyzing" if cv_ok else "unavailable",
            "duration":          None,
            "fps":               None,
            "frame_count":       None,
            "resolution":        None,
            "detected_objects":  [],
            "object_counts":     {},
            "event_timeline":    [],
            "confidence":        0.0,
        },
        created_at=now,
        updated_at=now,
    )

    item_dict = item.model_dump()
    embedding = embedding_service.embed_for_storage(original_name, placeholder_text)
    if embedding is not None:
        item_dict["embedding"] = embedding

    saved = memory_store.add(item_dict)
    logger.info("Video memory created: %s  video_id=%s  engine=%s", memory_id, video_id, analysis_engine)

    # Callback: update MemoryItem when analysis completes
    def _on_complete(results: dict) -> None:
        summary = results.get("summary", "")
        labels  = results.get("labels", [])
        tags    = list({"video", "cctv"} | set(labels))
        text    = summary or f"Video: {original_name}. {len(labels)} object type(s) detected."

        patch = {
            "text":  text,
            "tags":  tags,
            "metadata": {
                "original_filename": original_name,
                "file_size":         file_size,
                "video_id":          video_id,
                "analysis_engine":   results.get("analysis_engine", analysis_engine),
                "fallback_mode":     results.get("fallback_mode", fallback_mode),
                "analysis_status":   "done",
                "duration":          results.get("duration_secs"),
                "fps":               results.get("fps"),
                "frame_count":       results.get("frame_count"),
                "resolution":        results.get("resolution"),
                "detected_objects":  labels,
                "object_counts":     results.get("object_counts", {}),
                "event_timeline":    results.get("event_timeline", [])[:20],
                "confidence":        round(min(0.5 + 0.05 * len(labels), 0.95), 2),
            },
        }
        updated = memory_store.update(memory_id, patch)
        if updated:
            # Re-embed with richer summary text
            new_emb = embedding_service.embed_for_storage(original_name, text)
            if new_emb is not None:
                memory_store.update_embedding(memory_id, new_emb)
            logger.info("Video memory updated after analysis: %s  labels=%s", memory_id, labels)

    if cv_ok:
        start_analysis(video_id, str(saved_path), video_store, on_complete=_on_complete)

    return {
        "success":      True,
        "memory_id":    memory_id,
        "video_id":     video_id,
        "status":       "analyzing" if cv_ok else "unavailable",
        "yolo_active":  yolo_ok,
        "fallback_mode": fallback_mode,
        "memory":       saved,
    }
