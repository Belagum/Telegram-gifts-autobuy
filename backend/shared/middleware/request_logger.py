# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import hashlib
import time
from typing import Any

from flask import Flask, request, g

from backend.shared.config import load_config
from backend.shared.logging import logger, set_correlation_id, clear_correlation_id


def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    return request.remote_addr or "unknown"


def _get_user_id() -> int | None:
    return getattr(g, "user_id", None)


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    sensitive_headers = {
        "authorization", "cookie", "x-api-key", "x-auth-token",
        "x-csrf-token", "x-session-id"
    }
    
    sanitized = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower in sensitive_headers:
            sanitized[key] = f"<hashed:{hashlib.sha256(value.encode()).hexdigest()[:8]}>"
        else:
            sanitized[key] = value
    
    return sanitized


def _sanitize_query_params(params: dict[str, Any]) -> dict[str, Any]:
    sensitive_params = {"password", "token", "key", "secret", "auth"}
    
    sanitized = {}
    for key, value in params.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_params):
            sanitized[key] = "<redacted>"
        else:
            sanitized[key] = value
    
    return sanitized


def _log_request_start(debug_mode: bool) -> None:
    ip_address = _get_client_ip()
    user_id = _get_user_id()
    
    if debug_mode:
        headers = _sanitize_headers(dict(request.headers))
        query_params = _sanitize_query_params(dict(request.args))
        
        logger.info(
            f"Request started: {request.method} {request.path} "
            f"from {ip_address}, user={user_id}, "
            f"query={query_params}, headers={headers}, "
            f"body_size={len(request.data)}"
        )
    else:
        # Minimal logging
        logger.info(f"Request: {request.method} {request.path} from {ip_address}")


def _log_request_end(debug_mode: bool, start_time: float) -> None:
    duration = time.time() - start_time
    status_code = getattr(g, "response_status", 200)
    ip_address = _get_client_ip()
    user_id = _get_user_id()
    
    if debug_mode:
        logger.info(
            f"Request completed: {request.method} {request.path} "
            f"status={status_code}, duration={duration:.3f}s, "
            f"from {ip_address}, user={user_id}"
        )
    else:
        logger.info(
            f"Response: {request.method} {request.path} "
            f"status={status_code}, duration={duration:.3f}s"
        )


def configure_request_logging(app: Flask) -> None:
    config = load_config()
    debug_mode = config.debug_logging
    
    @app.before_request
    def _before_request() -> None:
        import secrets
        correlation_id = secrets.token_urlsafe(8)
        set_correlation_id(correlation_id)
        
        g.request_start_time = time.time()
        
        _log_request_start(debug_mode)
    
    @app.after_request
    def _after_request(response) -> None:
        g.response_status = response.status_code
        
        start_time = getattr(g, "request_start_time", time.time())
        _log_request_end(debug_mode, start_time)
        
        clear_correlation_id()
        
        return response
    
    @app.teardown_request
    def _teardown_request(exc: Exception | None) -> None:
        if exc is not None:
            ip_address = _get_client_ip()
            user_id = _get_user_id()
            
            if debug_mode:
                logger.exception(
                    f"Request error: {request.method} {request.path} "
                    f"from {ip_address}, user={user_id}, "
                    f"query={dict(request.args)}"
                )
            else:
                logger.error(
                    f"Request error: {type(exc).__name__} on "
                    f"{request.method} {request.path}"
                )
        
        clear_correlation_id()


__all__ = ["configure_request_logging"]
