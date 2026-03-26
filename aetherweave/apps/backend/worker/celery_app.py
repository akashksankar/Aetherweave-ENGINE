"""AetherWeave Backend — Celery worker application."""

from __future__ import annotations

from celery import Celery

from apps.backend.core.config import settings

celery_app = Celery(
    "aetherweave",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["apps.backend.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,       # acknowledge only after task completion
    worker_prefetch_multiplier=1,  # fair scheduling for long-running evolution tasks
)
