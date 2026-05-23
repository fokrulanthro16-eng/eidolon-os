"""
Celery ingestion tasks.
These run in the 3.12 venv worker process — full PaddleOCR + embed access.
"""
import asyncio
import logging
from pathlib import Path

from apps.api.workers.celery_app import app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async code in a sync Celery task context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(
    bind=True,
    name="apps.api.workers.tasks.ingest.ingest_image_task",
    max_retries=3,
    default_retry_delay=10,
    priority=5,
)
def ingest_image_task(self, image_path: str, source_type: str = "screenshot",
                      source_app: str | None = None, window_title: str | None = None) -> dict:
    """
    Load image from disk, run OCR + embed + store.
    Called by CaptureTask after saving screenshot to disk.
    """
    async def _run():
        from PIL import Image
        from apps.api.db.database import AsyncSessionLocal
        from apps.api.engines.memory.ingestion import ingest_image

        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        image = Image.open(path)

        async with AsyncSessionLocal() as db:
            record = await ingest_image(
                image=image,
                db=db,
                source_type=source_type,
                source_path=image_path,
                source_app=source_app,
                window_title=window_title,
            )
        return {"record_id": record.id, "chunk_count": record.chunk_count}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error("ingest_image_task failed: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    name="apps.api.workers.tasks.ingest.ingest_text_task",
    max_retries=2,
    priority=5,
)
def ingest_text_task(self, text: str, source_type: str = "note",
                     source_app: str | None = None, window_title: str | None = None) -> dict:
    async def _run():
        from apps.api.db.database import AsyncSessionLocal
        from apps.api.engines.memory.ingestion import ingest_text

        async with AsyncSessionLocal() as db:
            record = await ingest_text(
                text=text, db=db,
                source_type=source_type,
                source_app=source_app,
                window_title=window_title,
            )
        return {"record_id": record.id, "chunk_count": record.chunk_count}

    try:
        return _run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
