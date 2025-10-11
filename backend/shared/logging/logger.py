# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import logging
import os
import sys
import uuid
from contextvars import ContextVar

from loguru import logger as _logger

_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<lvl>{level:<8}</lvl> | "
    "<magenta>{extra[correlation_id]}</magenta> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<lvl>{message}</lvl>"
)

_CORRELATION_ID: ContextVar[str] = ContextVar("correlation_id", default="-")


def _log_file_path() -> str:
    base = os.getenv("LOG_FILE")
    if base:
        return base
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../instance"))
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "app.log")


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)
        _logger.opt(depth=6, exception=record.exc_info).log(
            level,
            record.getMessage(),
            correlation_id=_CORRELATION_ID.get(),
        )


class ContextualLogger:

    def __getattr__(self, name):  # pragma: no cover
        bound = _logger.bind(correlation_id=_CORRELATION_ID.get())
        return getattr(bound, name)


def set_correlation_id(value: str | None) -> None:
    _CORRELATION_ID.set(value or "-")


def get_correlation_id() -> str:
    return _CORRELATION_ID.get()


def clear_correlation_id() -> None:
    _CORRELATION_ID.set("-")


def setup_logging(level: str | None = None) -> None:
    level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    log_file = _log_file_path()
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    _logger.remove()
    _logger.add(
        sys.stderr,
        level=level,
        format=_FMT,
        colorize=True,
        backtrace=False,
        diagnose=False,
    )
    _logger.add(
        log_file,
        level=level,
        format=_FMT,
        colorize=False,
        backtrace=False,
        diagnose=False,
        enqueue=True,
        mode="w",
        encoding="utf-8",
    )

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


logger = ContextualLogger()

__all__ = [
    "logger",
    "setup_logging",
    "bind_flask",
    "set_correlation_id",
    "clear_correlation_id",
    "get_correlation_id",
]
