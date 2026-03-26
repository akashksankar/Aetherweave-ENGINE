"""
AetherWeave — Celery Beat auto-evolution scheduler
===================================================

Defines the periodic task schedule for Celery Beat.
Beat is the scheduler process that fires tasks on a timed cadence.

Start with:
    uv run celery -A apps.backend.worker.celery_app beat \
        --loglevel=info --scheduler celery.beat:PersistentScheduler

Scheduled tasks
---------------
  auto_snapshot every 5 minutes:
    Runs a short (5 generation) evolution on any architecture that
    hasn't been evolved in the last hour. This keeps idle graphs
    "alive" — they slowly improve even without user interaction.

  health_ping every 60 seconds:
    A lightweight heartbeat task that publishes a system:events ping
    so the frontend knows the Celery worker is alive.

  cleanup_symbiosis_tokens every 6 hours:
    Deletes expired symbiosis tokens from PostgreSQL.
"""

from __future__ import annotations

from celery.schedules import crontab

from apps.backend.worker.celery_app import celery_app

# ── Beat schedule ──────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    "health-ping": {
        "task":     "tasks.health_ping",
        "schedule": 60.0,  # every 60 seconds
        "options":  {"expires": 55},
    },
    "cleanup-symbiosis-tokens": {
        "task":     "tasks.cleanup_symbiosis_tokens",
        "schedule": crontab(minute=0, hour="*/6"),  # every 6 hours
        "options":  {"expires": 300},
    },
    "auto-snapshot-idle-archs": {
        "task":     "tasks.auto_snapshot_idle_architectures",
        "schedule": crontab(minute="*/5"),   # every 5 minutes
        "options":  {"expires": 240},
    },
}

celery_app.conf.timezone = "UTC"
