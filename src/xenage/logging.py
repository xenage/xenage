from __future__ import annotations

import sys

from loguru import logger


def configure_logging(level: str) -> None:
    resolved_level = level.upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=resolved_level,
        enqueue=False,
        backtrace=False,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
    )
    logger.debug("logging configured level={}", resolved_level)
