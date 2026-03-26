"""
AetherWeave Backend — Structured Logging Configuration
=======================================================

Configures structlog for both development (coloured, human-readable)
and production (JSON line, machine-parseable) output.

Call `configure_logging()` once at application startup in main.py.
All other modules then call `structlog.get_logger(__name__)` to get
a bound logger with automatic context injection.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, json_logs: bool = False, log_level: str = "INFO") -> None:
    """
    Configure structlog and the stdlib root logger.

    For JSON logs (production), each line is a single JSON object that can
    be ingested by log aggregators (Datadog, Loki, CloudWatch, etc.).

    For human-readable logs (development), output is coloured and indented
    for easy terminal reading.

    Args:
        json_logs: If True, emit JSON-formatted log lines.
        log_level: Minimum log level string (e.g. "DEBUG", "INFO", "WARNING").
    """
    # ── Shared processors (run for every log call) ─────────────────────
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: coloured console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # ── Configure stdlib root logger so uvicorn/celery logs are captured
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(log_level.upper()),
    )
    # Silence noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine", "celery.worker.consumer"):
        logging.getLogger(name).setLevel(logging.WARNING)
