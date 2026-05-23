"""
Celery Beat — periodic task scheduler.
Drives the continuous screen capture loop via schedule rather than a spinning async task.
This is more resilient than asyncio loops: survives worker restarts, supports rate control.

Run alongside workers:
  celery -A apps.api.workers.celery_app beat --loglevel=info
"""
from celery.schedules import crontab

from apps.api.config import settings
from apps.api.workers.celery_app import app

app.conf.beat_schedule = {
    "capture-screen": {
        "task": "apps.api.workers.tasks.capture.capture_screen_task",
        "schedule": settings.capture_interval_seconds,
        "options": {"queue": "eidolon.capture", "priority": 9},
    },
}

app.conf.beat_max_loop_interval = 5
