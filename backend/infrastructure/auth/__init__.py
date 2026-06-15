# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import inspect
from datetime import UTC, datetime
from functools import wraps
from typing import cast

from flask import Request, jsonify, request

from backend.infrastructure.db import get_db
from backend.infrastructure.db.models import SessionToken
from backend.shared.logging import logger


class AuthedRequest(Request):
    user_id: int


def authed_request() -> AuthedRequest:
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
            try:
                sig = inspect.signature(f)
                params = sig.parameters
                if "db" in params:
                    kw["db"] = db
                elif "_db" in params:
                    kw["_db"] = db
            except Exception:
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
