"""
Structured JSON logging with request-ID propagation.

Uses *structlog* for machine-readable log output in production and
human-friendly coloured output during development.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

# Context variable for request-scoped trace IDs.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def _add_request_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Inject the current request ID into every log record."""
    rid = request_id_ctx.get("")
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def generate_request_id() -> str:
    """Create a short, unique request identifier."""
    return uuid.uuid4().hex[:12]


def setup_logging(log_level: str = "INFO", json_logs: bool = False) -> None:
    """
    Configure structlog + stdlib logging.

    Parameters
    ----------
    log_level:
        Root log level (DEBUG, INFO, WARNING, …).
    json_logs:
        If *True* render every log event as a single JSON line
        (recommended for production).  Otherwise use coloured,
        human-readable console output.
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # Remove existing handlers to avoid duplicates on re-init.
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Quieten noisy third-party loggers.
    for name in ("uvicorn.access", "httpcore", "httpx", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a named structlog logger."""
    return structlog.get_logger(name)
