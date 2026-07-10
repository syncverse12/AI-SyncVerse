"""
Structured logging setup, shared by every layer.

Business code never configures logging itself — it just does
`logger = logging.getLogger(__name__)` and calls `logger.info(...)`.
This module is imported once at startup (from main.py) to wire the
formatting and handlers.
"""

import logging
import sys
import time
from contextlib import contextmanager


class JsonLikeFormatter(logging.Formatter):
    """Compact single-line format that's still easy to grep/parse."""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f'{{"ts": "{self.formatTime(record)}", '
            f'"level": "{record.levelname}", '
            f'"logger": "{record.name}", '
            f'"message": "{record.getMessage()}"'
        )
        for key in ("event", "duration_ms", "endpoint", "attempt", "provider", "project_id"):
            if hasattr(record, key):
                base += f', "{key}": {getattr(record, key)!r}'
        return base + "}"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLikeFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


@contextmanager
def log_duration(logger: logging.Logger, event: str, **extra):
    """
    Usage:
        with log_duration(logger, "llm_call", provider="gemini"):
            await call_llm(...)

    Logs one line with `duration_ms` regardless of success or failure, and
    re-raises any exception untouched.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(event, extra={"event": event, "duration_ms": duration_ms, **extra})
