"""
Celery application configuration for EIDOLON OS.

Queue priority:
  eidolon.capture  (9) — must be fast; blocks next capture cycle
  eidolon.ingest   (5) — normal priority; OCR + embed
  eidolon.vision   (3) — lowest; Qwen2-VL is slow, non-blocking

Windows note: run workers with --pool=solo (single-threaded) for dev.
  celery -A apps.api.workers.celery_app worker --pool=solo -Q eidolon.ingest,eidolon.capture,eidolon.vision

Production (Linux): remove --pool=solo for multiprocessing.
"""
from celery import Celery

from apps.api.config import settings

app = Celery(
    "eidolon",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "apps.api.workers.tasks.ingest",
        "apps.api.workers.tasks.capture",
        "apps.api.workers.tasks.vision",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,                  # re-queue on worker crash
    worker_prefetch_multiplier=1,         # one task at a time per worker
    task_routes={
        "apps.api.workers.tasks.capture.*": {"queue": "eidolon.capture"},
        "apps.api.workers.tasks.ingest.*":  {"queue": "eidolon.ingest"},
        "apps.api.workers.tasks.vision.*":  {"queue": "eidolon.vision"},
    },
    task_queue_max_priority=10,
    task_default_priority=5,
    broker_transport_options={
        "priority_steps": list(range(10)),
        "sep": ":",
        "queue_order_strategy": "priority",
    },
    result_expires=86400,                 # results expire after 24h
)
