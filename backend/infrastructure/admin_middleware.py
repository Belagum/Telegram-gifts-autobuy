# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from http import HTTPStatus
from typing import Any

from flask import g, request

from backend.infrastructure.db.models import SessionToken, User
from backend.infrastructure.db.session import SessionLocal
from backend.shared.config import load_config
from backend.shared.errors.base import AppError
from backend.shared.logging import logger


class AdminAccessDeniedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="admin_access_denied",
            status=HTTPStatus.FORBIDDEN,
        )


class AdminAuthenticationError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="admin_authentication_required",
            status=HTTPStatus.UNAUTHORIZED,
        )


def _get_current_user() -> User | None:
    config = load_config()
    debug_mode = config.debug_logging

    token_value = request.cookies.get("auth_token")

    if not token_value:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token_value = auth_header[7:]

    if not token_value:
        if debug_mode:
            logger.debug("No auth token found in request")
        return None

    db = SessionLocal()
    try:
        if debug_mode:
            import hashlib

            token_hash = hashlib.sha256(token_value.encode()).hexdigest()[:8]
            logger.debug(f"Validating token: <hash:{token_hash}>")

        token = db.query(SessionToken).filter(SessionToken.token == token_value).first()

        if not token:
            if debug_mode:
                logger.debug(f"Token not found in database: <hash:{token_hash}>")
            return None

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < now:
            if debug_mode:
                logger.debug(
                    f"Token expired: <hash:{token_hash}>, expires_at={token.expires_at}"
                )
            return None

        user = db.query(User).filter(User.id == token.user_id).first()

        if debug_mode:
            user_id = user.id if user else None
            is_admin = user.is_admin if user else None
            logger.debug(
                f"Token valid, user found: user_id={user_id}, is_admin={is_admin}"
            )

        return user

    finally:
        db.close()


def require_admin(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        config = load_config()
        debug_mode = config.debug_logging

        user = _get_current_user()

        if not user:
            if debug_mode:
                method = request.method
                path = request.path
                logger.warning(
                    f"Admin access denied: no authentication on {method} {path}"
                )
            raise AdminAuthenticationError()

        if not user.is_admin:
            if debug_mode:
                method = request.method
                path = request.path
                logger.warning(
                    f"Admin access denied: user {user.id} ({user.username}) is not admin on {method} {path}"
                )
            else:
                logger.warning(f"Admin access denied: user {user.id} is not admin")
            raise AdminAccessDeniedError()

        if debug_mode:
            method = request.method
            path = request.path
            logger.debug(
                f"Admin access granted: user {user.id} ({user.username}) on {method} {path}"
            )

        g.user_id = user.id
        g.debug_mode = debug_mode

        return func(*args, **kwargs)

    return wrapper


__all__ = [
    "require_admin",
    "AdminAccessDeniedError",
    "AdminAuthenticationError",
]
