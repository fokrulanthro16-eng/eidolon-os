import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.db.database import get_db
from apps.api.db.models import CaptureEvent
from apps.api.models.schemas import CaptureStatusResponse, IngestResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/capture", tags=["capture"])

# Capture state tracked in-process (Beat scheduler owns periodic capture)
_last_capture_at = None


@router.post("/trigger", response_model=IngestResponse)
async def trigger_capture(db: AsyncSession = Depends(get_db)):
    """Manual one-shot capture — bypasses Celery for immediate response."""
    from PIL import Image
    from apps.api.engines.neurovision.screen_capture import capture_screen, save_screenshot
    from apps.api.engines.memory.ingestion import ingest_image

    frame = await asyncio.to_thread(capture_screen, settings.capture_max_width)
    saved_path = await asyncio.to_thread(save_screenshot, frame.image, settings.screenshots_dir)

    record = await ingest_image(
        image=frame.image, db=db, source_type="screenshot",
        source_path=str(saved_path), source_app=frame.source_app,
        window_title=frame.window_title,
    )
    return IngestResponse(
        record_id=record.id, chunk_count=record.chunk_count,
        ocr_confidence=record.ocr_confidence,
        message=f"Captured: {frame.window_title or 'unknown'}",
    )


@router.post("/start")
async def start_capture():
    """Start periodic capture via Celery Beat — sends a signal to the scheduler."""
    try:
        from apps.api.workers.tasks.capture import capture_screen_task
        capture_screen_task.apply_async(queue="eidolon.capture", priority=9)
        return {"status": "triggered", "message": "Periodic capture runs via Celery Beat. Ensure Beat is running."}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Celery unavailable: {e}")


@router.post("/stop")
async def stop_capture():
    return {"status": "stopped", "message": "Revoke via Celery inspect or stop Beat process."}


@router.get("/status", response_model=CaptureStatusResponse)
async def capture_status(db: AsyncSession = Depends(get_db)):
    from datetime import date, timezone
    today = date.today()
    total_today = (
        await db.execute(
            select(func.count()).select_from(CaptureEvent)
            .where(CaptureEvent.captured_at >= today)
        )
    ).scalar_one()

    last_event = (
        await db.execute(
            select(CaptureEvent)
            .order_by(CaptureEvent.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return CaptureStatusResponse(
        running=settings.capture_enabled,
        interval_seconds=settings.capture_interval_seconds,
        last_capture_at=last_event.captured_at if last_event else None,
        total_captures_today=total_today,
    )
