# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from http import HTTPStatus

from flask import Response, jsonify

from .base import AppError

from werkzeug.exceptions import HTTPException
from backend.shared.config import load_config
from backend.shared.logging import logger

def handle_app_error(error: AppError) -> tuple[Response, HTTPStatus]:
    response = jsonify(error.to_dict())
    return response, error.status


def register_error_handler(
    app, *, default_status: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR
) -> None:


    config = load_config()
    debug_mode = config.debug_logging

    @app.errorhandler(AppError)
    def _handle_app_error(exc: AppError):
        return handle_app_error(exc)

    @app.errorhandler(HTTPException)
    def _handle_http(exc: HTTPException):
        return exc

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        from flask import request, g
        
        ip_address = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() if request.headers.get("X-Forwarded-For") else (request.remote_addr or "unknown")
        user_id = getattr(g, "user_id", None)
        
        if debug_mode:
            logger.exception(
                f"Unhandled exception: {request.method} {request.path} "
                f"from {ip_address}, user={user_id}, "
                f"query={dict(request.args)}, body_size={len(request.data)}"
            )
        else:
            logger.error(f"Error: {type(exc).__name__} on {request.method} {request.path}")
        
        response = jsonify({"error": "internal_error"})
        return response, default_status
