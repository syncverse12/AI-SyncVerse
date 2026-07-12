"""
core/logging.py
----------------
Structured logging, independent of business logic. Every layer imports
`get_logger(__name__)` and logs plain messages + `extra=` fields; this
module owns *how* those get formatted (JSON-ish key=value for easy
grepping on Railway's log viewer).
"""

from __future__ import annotations
import logging
import sys
import time
from contextlib import contextmanager
from typing import Iterator

from app.config import get_settings

_CONFIGURED = False


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.Formatter) -> str:  # type: ignore[override]
        base = (
            f"ts={self.formatTime(record, '%Y-%m-%dT%H:%M:%S')} "
            f"level={record.levelname} logger={record.name} "
            f"msg=\"{record.getMessage()}\""
        )
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            )
        }
        if extras:
            base += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KeyValueFormatter())
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    root.handlers = [handler]
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


@contextmanager
def timed(logger: logging.Logger, operation: str, **fields) -> Iterator[None]:
    """Logs execution time for any block: `with timed(logger, "llm_call"): ...`"""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            f"{operation} completed",
            extra={"operation": operation, "duration_ms": duration_ms, **fields},
        )
