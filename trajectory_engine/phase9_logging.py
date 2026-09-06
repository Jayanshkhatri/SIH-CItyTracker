"""Safe structured logging and lightweight timing for the Phase 9 boundary."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Iterator


LOGGER_NAME = "sih26127"


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure one non-secret-bearing application logger, idempotently."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = configure_logging()


def request_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def timed(operation: str, **context: object) -> Iterator[None]:
    """Log duration and safe metadata; callers must not pass secret values."""
    started = time.perf_counter()
    try:
        yield
    except Exception:
        logger.exception("operation_failed operation=%s context=%s", operation, context)
        raise
    else:
        logger.info(
            "operation_completed operation=%s duration_ms=%.3f context=%s",
            operation,
            (time.perf_counter() - started) * 1000,
            context,
        )
