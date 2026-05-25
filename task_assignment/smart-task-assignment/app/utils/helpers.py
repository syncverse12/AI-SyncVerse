"""Shared utility functions."""
import uuid
import logging
import sys


def generate_task_id() -> str:
    """Generate a short unique task identifier."""
    return str(uuid.uuid4())[:8]


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s – %(message)s",
        datefmt="%H:%M:%S",
    )
