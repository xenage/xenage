from __future__ import annotations

import os
import sys

from loguru import logger


LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
    "pid={process.id} tid={thread.id} | {name}:{function}:{line} | {message}"
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_logging(level: str, *, json_logs: bool | None = None) -> None:
    resolved_level = level.upper().strip()
    serialize = _env_flag("XENAGE_LOG_JSON", False) if json_logs is None else json_logs
    enqueue = _env_flag("XENAGE_LOG_ENQUEUE", False)
    logger.remove()
    logger.add(
        sys.stderr,
        level=resolved_level,
        enqueue=enqueue,
        backtrace=False,
        diagnose=False,
        serialize=serialize,
        format=LOG_FORMAT,
    )
    logger.debug(
        "logging configured level={} serialize={} enqueue={}",
        resolved_level,
        serialize,
        enqueue,
    )
