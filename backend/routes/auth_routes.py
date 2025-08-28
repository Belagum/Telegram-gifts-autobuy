# backend/routes/auth_routes.py
from time import perf_counter
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, SessionToken
from ..auth import hash_password, verify_password, issue_token, auth_required
from ..logger import logger

bp_auth = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp_auth.post("/register", strict_slashes=False)
def register():
    from flask import make_response
    t0 = perf_counter()
    db_gen = get_db(); db = next(db_gen)
    req_id = id(db)
    try:
        d = request.get_json(silent=True) or {}
        u = (d.get("username") or "").strip()
        p = d.get("password") or ""
        logger.info("auth.register: start (req_id={}, username='{}')", req_id, u)
        if not u or not p:
            logger.warning("auth.register: missing fields (req_id={}, username='{}')", req_id, u)
            return jsonify({"error": "username_and_password_required"}), 400
        if db.query(User).filter(User.username == u).first():
            logger.warning("auth.register: username taken (req_id={}, username='{}')", req_id, u)
            return jsonify({"error": "username_taken"}), 409
        user = User(username=u, password_hash=hash_password(p))
        db.add(user); db.commit()
        token = issue_token(db, user.id)
        dt = (perf_counter() - t0) * 1000
        logger.info("auth.register: ok (req_id={}, user_id={}, dt_ms={:.0f})", req_id, user.id, dt)
        resp = make_response(jsonify({"ok": True}))
        resp.set_cookie("auth_token", token, httponly=True, samesite="Lax", secure=False, max_age=60*60*24*7)
        return resp
    except Exception:
        logger.exception("auth.register: error (req_id={}, username='{}')", req_id, (locals().get("u") or ""))
        return jsonify({"error": "internal_error"}), 500
    finally:
        try: db_gen.close()
        except Exception: logger.debug("auth.register: db_gen.close failed (req_id={})", req_id)


@bp_auth.post("/login", strict_slashes=False)
def login():
    from flask import make_response
    t0 = perf_counter()
    db_gen = get_db(); db = next(db_gen)
    req_id = id(db)
    try:
        d = request.get_json(silent=True) or {}
        u = (d.get("username") or "").strip()
        p = d.get("password") or ""
        logger.info("auth.login: start (req_id={}, username='{}')", req_id, u)
        user = db.query(User).filter(User.username == u).first()
        if not user or not verify_password(user.password_hash, p):
            logger.warning("auth.login: invalid credentials (req_id={}, username='{}')", req_id, u)
            return jsonify({"error": "invalid_credentials"}), 401
        token = issue_token(db, user.id)
        dt = (perf_counter() - t0) * 1000
        logger.info("auth.login: ok (req_id={}, user_id={}, dt_ms={:.0f})", req_id, user.id, dt)
        resp = make_response(jsonify({"ok": True}))
        resp.set_cookie("auth_token", token, httponly=True, samesite="Lax", secure=False, max_age=60*60*24*7)
        return resp
    except Exception:
        logger.exception("auth.login: error (req_id={}, username='{}')", req_id, (locals().get("u") or ""))
        return jsonify({"error": "internal_error"}), 500
    finally:
        try: db_gen.close()
        except Exception: logger.debug("auth.login: db_gen.close failed (req_id={})", req_id)



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
        logger.info("auth.logout: start (req_id={}, user_id={}, token='{}')", req_id, getattr(request, "user_id", None), token_hint)
        if token:
            db.query(SessionToken).filter(SessionToken.token == token).delete()
            db.commit()
        dt = (perf_counter() - t0) * 1000
        logger.info("auth.logout: ok (req_id={}, user_id={}, dt_ms={:.0f})", req_id, getattr(request, "user_id", None), dt)
        resp = make_response(jsonify({"ok": True}))
        resp.delete_cookie("auth_token")
        return resp
    except Exception:
        logger.exception("auth.logout: error (req_id={}, user_id={})", req_id, getattr(request, "user_id", None))
        return jsonify({"error": "internal_error"}), 500
