"""Structured logging configuration for the OCR command boundary."""

import logging
from functools import lru_cache

import structlog
from structlog.stdlib import BoundLogger


@lru_cache(maxsize=1)
def configure_logging() -> None:
    """Configure stable JSON events once for the current process."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=(
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger() -> BoundLogger:
    """Return the configured OCR command logger."""
    configure_logging()
    return structlog.stdlib.get_logger("ocr")
