# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

from time import perf_counter

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session

from ..auth import auth_required, hash_password, issue_token, verify_password
from ..db import get_db
from ..logger import logger
from ..models import SessionToken, User

bp_auth = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp_auth.post("/register", strict_slashes=False)
def register():
    from flask import make_response

    t0 = perf_counter()
    db_gen = get_db()
    db = next(db_gen)
    req_id = id(db)
    try:
        d = request.get_json(silent=True) or {}
        u = (d.get("username") or "").strip()
        p = d.get("password") or ""
        logger.info(f"auth.register: start (req_id={req_id}, username='{u}')")
        if not u or not p:
            logger.warning(f"auth.register: missing fields (req_id={req_id}, username='{u}')")
            return jsonify({"error": "username_and_password_required"}), 400
        if db.query(User).filter(User.username == u).first():
            logger.warning(f"auth.register: username taken (req_id={req_id}, username='{u}')")
            return jsonify({"error": "username_taken"}), 409
        user = User(username=u, password_hash=hash_password(p))
        db.add(user)
        db.commit()
        token = issue_token(db, user.id)
        dt = (perf_counter() - t0) * 1000
        logger.info(f"auth.register: ok (req_id={req_id}, user_id={user.id}, dt_ms={dt:.0f})")
        resp = make_response(jsonify({"ok": True}))
        resp.set_cookie(
            "auth_token",
            token,
            httponly=True,
            samesite="Lax",
            secure=False,
            max_age=60 * 60 * 24 * 7,
        )
        return resp
    except Exception:
        logger.exception(
            f"auth.register: error (req_id={req_id}, username='{locals().get('u') or ''}')"
        )
        return jsonify({"error": "internal_error"}), 500
    finally:
        try:
            db_gen.close()
        except Exception:
            logger.debug(f"auth.register: db_gen.close failed (req_id={req_id})")


@bp_auth.post("/login", strict_slashes=False)
def login():
    from flask import make_response

    t0 = perf_counter()
    db_gen = get_db()
    db = next(db_gen)
    req_id = id(db)
    try:
        d = request.get_json(silent=True) or {}
        u = (d.get("username") or "").strip()
        p = d.get("password") or ""
        logger.info(f"auth.login: start (req_id={req_id}, username='{u}')")
        user = db.query(User).filter(User.username == u).first()
        if not user or not verify_password(user.password_hash, p):
            logger.warning(f"auth.login: invalid credentials (req_id={req_id}, username='{u}')")
            return jsonify({"error": "invalid_credentials"}), 401
        token = issue_token(db, user.id)
        dt = (perf_counter() - t0) * 1000
        logger.info(f"auth.login: ok (req_id={req_id}, user_id={user.id}, dt_ms={dt:.0f})")
        resp = make_response(jsonify({"ok": True}))
        resp.set_cookie(
            "auth_token",
            token,
            httponly=True,
            samesite="Lax",
            secure=False,
            max_age=60 * 60 * 24 * 7,
        )
        return resp
    except Exception:
        logger.exception(
            f"auth.login: error (req_id={req_id}, username='{locals().get('u') or ''}')"
        )
        return jsonify({"error": "internal_error"}), 500
    finally:
        try:
            db_gen.close()
        except Exception:
            logger.debug(f"auth.login: db_gen.close failed (req_id={req_id})")


@bp_auth.delete("/logout", strict_slashes=False)
@auth_required
def logout(db: Session):
    from flask import make_response

    t0 = perf_counter()
    req_id = id(db)
    try:
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else request.cookies.get("auth_token", "")
        token_hint = (token[:6] + "...") if token else ""
        logger.info(
            "auth.logout: start (req_id=%s, user_id=%s, token='%s')",
            req_id,
            getattr(request, "user_id", None),
            token_hint,
        )
        if token:
            db.query(SessionToken).filter(SessionToken.token == token).delete()
            db.commit()
        dt = (perf_counter() - t0) * 1000
        logger.info(
            "auth.logout: ok (req_id=%s, user_id=%s, dt_ms=%.0f)",
            req_id,
            getattr(request, "user_id", None),
            dt,
        )
        resp = make_response(jsonify({"ok": True}))
        resp.delete_cookie("auth_token")
        return resp
    except Exception:
        logger.exception(
            f"auth.logout: error (req_id={req_id}, user_id={getattr(request, 'user_id', None)})"
        )
        return jsonify({"error": "internal_error"}), 500
