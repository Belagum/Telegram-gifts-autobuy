# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import secrets
from collections.abc import Callable
from functools import wraps

from flask import Flask, jsonify, request

from backend.shared.config import load_config

SAFE_METHODS: tuple[str, ...] = ("GET", "HEAD", "OPTIONS")


def _is_enabled() -> bool:
    return load_config().security.enable_csrf


def configure_csrf(app: Flask) -> None:
    if not _is_enabled():
        return

    @app.after_request
    def _ensure_csrf_cookie(resp):
        if request.method in SAFE_METHODS:
            token = request.cookies.get("csrf_token", "")
            if not token:
                token = secrets.token_urlsafe(32)
                config = load_config()
                resp.set_cookie(
                    "csrf_token",
                    token,
                    httponly=False,
                    samesite=config.security.cookie_samesite,
                    secure=config.security.cookie_secure,
                    max_age=60 * 60 * 24 * 7,
                )
        return resp


def csrf_protect(f: Callable):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _is_enabled():
            return f(*args, **kwargs)
        if request.method in SAFE_METHODS:
            return f(*args, **kwargs)
        header = (request.headers.get("X-CSRF-Token") or "").strip()
        cookie = (request.cookies.get("csrf_token") or "").strip()
        if not header or not cookie or header != cookie:
            return jsonify({"error": "csrf"}), 403
        return f(*args, **kwargs)

    return wrapper


__all__ = ["configure_csrf", "csrf_protect"]
