# backend/auth.py
import secrets
from functools import wraps
from datetime import datetime, timezone

from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import Session

from .models import SessionToken, token_default_exp
from .db import get_db
from .logger import logger


def hash_password(p: str) -> str:
    return generate_password_hash(p)


def verify_password(h: str, p: str) -> bool:
    return check_password_hash(h, p)


def issue_token(db: Session, user_id: int) -> str:
    # один активный токен на пользователя
    db.query(SessionToken).filter(SessionToken.user_id == user_id).delete()
    token = secrets.token_urlsafe(48)
    row = SessionToken(
        user_id=user_id,
        token=token,
        expires_at=token_default_exp()
    )
    db.add(row)
    db.commit()

    logger.info(
        "Issued token for user={user_id} exp={exp} tok={tok}",
        user_id=user_id,
        exp=row.expires_at.isoformat(),
        tok=f"{token[:8]}…",
    )
    return token


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
                "No Authorization header/cookie on {m} {p} from {ip}",
                m=request.method, p=request.path,
                ip=request.headers.get("X-Forwarded-For", request.remote_addr),
            )
            return jsonify({"error": "unauthorized"}), 401

        db_gen = get_db(); db = next(db_gen)
        try:
            row = (
                db.query(SessionToken)
                .filter(
                    SessionToken.token == token,
                    SessionToken.expires_at > datetime.now(timezone.utc),
                )
                .first()
            )
            if not row:
                logger.warning("Auth failed (token not found/expired) on {m} {p}", m=request.method, p=request.path)
                return jsonify({"error": "unauthorized"}), 401

            request.user_id = row.user_id
            kw["db"] = db
            logger.debug("Auth OK: user={uid} {m} {p}", uid=row.user_id, m=request.method, p=request.path)
            return f(*a, **kw)
        except Exception:
            logger.exception("Unhandled error inside auth wrapper for {m} {p}", m=request.method, p=request.path)
            raise
        finally:
            try: db_gen.close()
            except Exception: logger.exception("Failed to close DB generator in auth wrapper")
    return inner