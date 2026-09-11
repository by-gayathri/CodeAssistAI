"""Structured logging helpers for CodeAssistAI."""

from __future__ import annotations

import logging
import sys
from typing import Any


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging for the application."""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level.upper())
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log a structured event without sensitive payloads.

    Never pass API keys, full source code, or full prompts via fields.
    """
    parts = [f"event={event}"]
    for key, value in fields.items():
        parts.append(f"{key}={value}")
    logger.info(" ".join(parts))
