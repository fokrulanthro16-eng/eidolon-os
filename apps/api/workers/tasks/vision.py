"""
Qwen2-VL visual analysis task — lowest priority.
Updates visual_summary on an existing MemoryRecord after initial ingest.
Runs asynchronously — doesn't block the ingestion result.
"""
import asyncio
import logging

from apps.api.workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(
    name="apps.api.workers.tasks.vision.analyze_record_task",
    priority=3,
    max_retries=2,
    default_retry_delay=30,
)
def analyze_record_task(record_id: str, image_path: str) -> dict:
    """Load image, run Qwen2-VL, update record visual_summary."""
    async def _run():
        from pathlib import Path
        from PIL import Image
        from sqlalchemy import select, update
        from apps.api.db.database import AsyncSessionLocal
        from apps.api.db.models import MemoryRecord
        from apps.api.engines.memory.vision.qwen_vl import analyze_screenshot

        path = Path(image_path)
        if not path.exists():
            return {"status": "skipped", "reason": "image_not_found"}

        image = Image.open(path)
        summary = await analyze_screenshot(image)

        if summary:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(MemoryRecord)
                    .where(MemoryRecord.id == record_id)
                    .values(visual_summary=summary)
                )
                await db.commit()

        return {"status": "ok", "had_summary": summary is not None}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
