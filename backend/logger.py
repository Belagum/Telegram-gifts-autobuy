# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import os
import sys
import logging
from loguru import logger as _logger

_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<lvl>{level:<8}</lvl> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<lvl>{message}</lvl>"
)

class _InterceptHandler(logging.Handler):
    _DROP_PREFIXES = ("pyrogram",)

    def emit(self, record: logging.LogRecord) -> None:
        if any(record.name.startswith(p) for p in self._DROP_PREFIXES):
            return  # игнорим полностью
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        _logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(level: str | None = None) -> None:
    level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()

    # Loguru sink
    _logger.remove()
    _logger.add(
        sys.stderr,
        level=level,
        format=_FMT,
        colorize=True,
        backtrace=False,
        diagnose=False,
        enqueue=False,
    )

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    logging.getLogger("werkzeug").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

def bind_flask(app) -> None:

    import time
    from flask import request, g, jsonify

    @app.before_request
    def _start_timer():
        g._t0 = time.perf_counter()

    @app.after_request
    def _log_response(resp):
        try:
            dt = (time.perf_counter() - getattr(g, "_t0", time.perf_counter())) * 1000.0
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            _logger.info(
                "{method} {path} -> {status} in {ms:.1f} ms from {ip}",
                method=request.method,
                path=request.path,
                status=resp.status_code,
                ms=dt,
                ip=ip,
            )
        except Exception:
            pass
        return resp

    @app.errorhandler(Exception)
    def _err(e):
        # Полный traceback + контекст запроса
        _logger.exception("Unhandled error on {method} {path}", method=request.method, path=request.path)
        return jsonify({"error": "internal_error"}), 500

logger = _logger
