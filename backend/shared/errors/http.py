# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from http import HTTPStatus

from flask import Response, jsonify

from .base import AppError


def handle_app_error(error: AppError) -> tuple[Response, HTTPStatus]:
    response = jsonify(error.to_dict())
    return response, error.status


def register_error_handler(
    app, *, default_status: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR
) -> None:
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(AppError)
    def _handle_app_error(exc: AppError):
        return handle_app_error(exc)

    @app.errorhandler(HTTPException)
    def _handle_http(exc: HTTPException):
        return exc

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        response = jsonify({"error": "internal_error", "message": "An unexpected error occurred"})
        return response, default_status


