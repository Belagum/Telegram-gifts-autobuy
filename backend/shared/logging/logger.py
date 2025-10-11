"""Structured logging utilities."""

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
    """Proxy for loguru that injects correlation ids via ContextVar."""

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


def bind_flask(app) -> None:
    import time

    from flask import g, jsonify, request, send_file
    from werkzeug.exceptions import HTTPException

    from backend.shared.errors.base import AppError

    @app.before_request
    def _start_timer() -> None:
        g._t0 = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g._correlation_id = request_id
        set_correlation_id(request_id)

    @app.after_request
    def _log_response(resp):
        try:
            dt = (time.perf_counter() - getattr(g, "_t0", time.perf_counter())) * 1000.0
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            logger.info(
                f"{request.method} {request.path} -> {resp.status_code} in {dt:.1f} ms from {ip}"
            )
        except Exception:
            pass
        return resp

    @app.teardown_request
    def _teardown(_exc):
        clear_correlation_id()

    @app.errorhandler(Exception)
    def _err(e: Exception):
        if isinstance(e, HTTPException):
            return e
        if isinstance(e, AppError):
            logger.warning(f"Handled application error {e.code} on {request.method} {request.path}")
            return jsonify(e.to_dict()), e.status
        logger.exception(f"Unhandled error on {request.method} {request.path}")
        return jsonify({"error": "internal_error"}), 500

    @app.get("/api/logs/download")
    def download_logs():
        log_file = _log_file_path()
        if not os.path.exists(log_file):
            return jsonify({"error": "log_file_not_found"}), 404
        return send_file(
            log_file,
            mimetype="text/plain",
            as_attachment=True,
            download_name="giftbuyer.log",
        )


logger = ContextualLogger()

__all__ = [
    "logger",
    "setup_logging",
    "bind_flask",
    "set_correlation_id",
    "clear_correlation_id",
    "get_correlation_id",
]
