"""
Celery capture task — high priority, fast.
Grabs screen → saves to disk → chains ingest task.
Separated from ingest so capture is never blocked by OCR/embed time.
"""
import logging

from celery import chain

from apps.api.workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(
    name="apps.api.workers.tasks.capture.capture_screen_task",
    priority=9,
    max_retries=1,
)
def capture_screen_task() -> dict:
    """Capture screen, save to storage, enqueue ingest."""
    from apps.api.config import settings
    from apps.api.engines.neurovision.screen_capture import capture_screen, save_screenshot

    try:
        frame = capture_screen(max_width=settings.capture_max_width)
        saved_path = save_screenshot(frame.image, settings.screenshots_dir)

        # Chain: this task → ingest_image_task (runs immediately after)
        from apps.api.workers.tasks.ingest import ingest_image_task
        ingest_image_task.apply_async(
            kwargs={
                "image_path": str(saved_path),
                "source_type": "screenshot",
                "source_app": frame.source_app,
                "window_title": frame.window_title,
            },
            queue="eidolon.ingest",
            priority=5,
        )

        return {
            "status": "captured",
            "path": str(saved_path),
            "source_app": frame.source_app,
            "window_title": frame.window_title,
        }
    except Exception as e:
        logger.error("capture_screen_task failed: %s", e)
        raise
