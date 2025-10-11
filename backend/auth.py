# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import secrets
from datetime import UTC, datetime
from functools import wraps
from typing import cast

from flask import Request, jsonify, request
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from backend.infrastructure.db import get_db
from backend.infrastructure.db.models import SessionToken, token_default_exp
from backend.shared.logging import logger


def hash_password(p: str) -> str:
    return str(generate_password_hash(p))


def verify_password(h: str, p: str) -> bool:
    return bool(check_password_hash(h, p))


def issue_token(db: Session, user_id: int) -> str:
    db.query(SessionToken).filter(SessionToken.user_id == user_id).delete()
    token = secrets.token_urlsafe(48)
    row = SessionToken(user_id=user_id, token=token, expires_at=token_default_exp())
    db.add(row)
    db.commit()

    logger.info(
        f"Issued token for user={user_id} exp={row.expires_at.isoformat()} tok={token[:8]}…"
    )
    return token


class AuthedRequest(Request):
    user_id: int


def authed_request() -> AuthedRequest:
    """Return the current request cast to include authentication attributes."""
    return cast(AuthedRequest, request)


def auth_required(f):
    @wraps(f)
    def inner(*a, **kw):
        auth = request.headers.get("Authorization", "")
        token = ""
        if auth.startswith("Bearer "):
            token = auth[7:]
        if not token:
            token = request.cookies.get("auth_token", "")

        if not token:
            logger.warning(
                f"No Authorization header/cookie on {request.method} {request.path} "
                f"from {request.headers.get('X-Forwarded-For', request.remote_addr)}"
            )
            return jsonify({"error": "unauthorized"}), 401

        db_gen = get_db()
        db = next(db_gen)
        try:
            row = (
                db.query(SessionToken)
                .filter(
                    SessionToken.token == token,
                    SessionToken.expires_at > datetime.now(UTC),
                )
                .first()
            )
            if not row:
                logger.warning(
                    f"Auth failed (token not found/expired) on {request.method} {request.path}"
                )
                return jsonify({"error": "unauthorized"}), 401

            request.user_id = row.user_id
            kw["db"] = db
            logger.debug(f"Auth OK: user={row.user_id} {request.method} {request.path}")
            return f(*a, **kw)
        except Exception:
            logger.exception(
                f"Unhandled error inside auth wrapper for {request.method} {request.path}"
            )
            raise
        finally:
            try:
                db_gen.close()
            except Exception:
                logger.exception("Failed to close DB generator in auth wrapper")

    return inner
