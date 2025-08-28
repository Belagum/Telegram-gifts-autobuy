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
    "<magenta>{process.name}:{thread.name}</magenta> - "
    "<lvl>{message}</lvl>"
)

class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        # поднимаемся выше внутренних стеков logging
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

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
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

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
