# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import json
import re
from time import perf_counter

from flask import Blueprint, Response, jsonify, request, stream_with_context
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import auth_required, authed_request
from ..db import SessionLocal
from ..logger import logger
from ..models import Account, ApiProfile, User
from ..pyro_login import PyroLoginManager
from ..services.accounts_service import (
    any_stale,
    begin_user_refresh,
    end_user_refresh,
    iter_refresh_steps_core,
    read_accounts,
    schedule_user_refresh,
    wait_until_ready,
)

bp_acc = Blueprint("accounts", __name__, url_prefix="/api")
_logins = PyroLoginManager()


def _norm_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    if not digits:
        return ""
    # 8 -> 7
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return "+" + digits


@bp_acc.get("/accounts", endpoint="accounts_list")
@auth_required
def accounts(db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    wait = request.args.get("wait") in ("1", "true", "yes")
    logger.info(f"accounts.list: start (user_id={uid}, wait={wait})")
    try:
        has_any = db.query(func.count(Account.id)).filter(Account.user_id == uid).scalar() or 0
        if not has_any:
            resp, code = jsonify({"state": "ready", "accounts": []}), 200
        else:
            if any_stale(db, uid):
                schedule_user_refresh(uid)
                if wait and wait_until_ready(uid, timeout_sec=25.0):
                    accs = read_accounts(db, uid)
                    resp, code = jsonify({"state": "ready", "accounts": accs}), 200
                else:
                    resp, code = jsonify({"state": "refreshing", "accounts": None}), 202
            else:
                accs = read_accounts(db, uid)
                resp, code = jsonify({"state": "ready", "accounts": accs}), 200
        resp.headers["Cache-Control"] = "no-store"
        dt = (perf_counter() - t0) * 1000
        status = "ready" if code == 200 else "refreshing"
        logger.info("accounts.list: %s (user_id=%s, dt_ms=%.0f)", status, uid, dt)
        return resp, code
    except Exception:
        logger.exception(f"accounts.list: error (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.get("/me", endpoint="me_info")
@auth_required
def me(db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    logger.info(f"me: start (user_id={uid})")
    try:
        u = db.get(User, uid)
        if not u:
            logger.warning("me: user_not_found (user_id=%s)", uid)
            return jsonify({"error": "not_found"}), 404
        dt = (perf_counter() - t0) * 1000
        logger.info(f"me: ok (user_id={uid}, username='{u.username}', dt_ms={dt:.0f})")
        return jsonify({"username": u.username})
    except Exception:
        logger.exception(f"me: error (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.get("/apiprofiles", endpoint="apiprofiles_list")
@auth_required
def list_api_profiles(db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    logger.info(f"apiprofiles.list: start (user_id={uid})")
    try:
        rows = (
            db.query(ApiProfile)
            .filter(ApiProfile.user_id == uid)
            .order_by(ApiProfile.id.desc())
            .all()
        )
        items = [{"id": r.id, "api_id": r.api_id, "name": r.name or ""} for r in rows]
        dt = (perf_counter() - t0) * 1000
        logger.info(f"apiprofiles.list: ok (user_id={uid}, count={len(items)}, dt_ms={dt:.0f})")
        return jsonify({"items": items})
    except Exception:
        logger.exception(f"apiprofiles.list: error (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/apiprofile", endpoint="apiprofile_create")
@auth_required
def create_apiprofile(db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    d = request.get_json(silent=True) or {}
    api_id, api_hash = d.get("api_id"), d.get("api_hash")
    name = (d.get("name") or "").strip() or None
    logger.info(f"apiprofile.create: start (user_id={uid}, api_id={api_id}, name='{name or ''}')")
    try:
        if not api_id or not api_hash:
            logger.warning(f"apiprofile.create: missing fields (user_id={uid})")
            return jsonify({"error": "api_id_and_api_hash_required"}), 400

        exist_id = (
            db.query(ApiProfile)
            .filter(ApiProfile.user_id == uid, ApiProfile.api_id == int(api_id))
            .first()
        )
        if exist_id:
            logger.warning(
                f"apiprofile.create: duplicate api_id (user_id={uid}, existing_id={exist_id.id})"
            )
            return jsonify({"error": "duplicate_api_id", "existing_id": exist_id.id}), 409

        exist_hash = (
            db.query(ApiProfile)
            .filter(ApiProfile.user_id == uid, ApiProfile.api_hash == str(api_hash))
            .first()
        )
        if exist_hash:
            logger.warning(
                "apiprofile.create: duplicate api_hash (user_id=%s, existing_id=%s)",
                uid,
                exist_hash.id,
            )
            return jsonify({"error": "duplicate_api_hash", "existing_id": exist_hash.id}), 409

        ap = ApiProfile(user_id=uid, api_id=int(api_id), api_hash=str(api_hash), name=name)
        db.add(ap)
        db.commit()

        dt = (perf_counter() - t0) * 1000
        logger.info(f"apiprofile.create: ok (user_id={uid}, id={ap.id}, dt_ms={dt:.0f})")
        return jsonify({"api_profile_id": ap.id})
    except Exception:
        logger.exception(f"apiprofile.create: error (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.patch("/apiprofile/<int:ap_id>", endpoint="apiprofile_rename")
@auth_required
def rename_apiprofile(ap_id: int, db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    logger.info(f"apiprofile.rename: start (user_id={uid}, ap_id={ap_id}, name='{name}')")
    try:
        ap = db.query(ApiProfile).filter(ApiProfile.id == ap_id, ApiProfile.user_id == uid).first()
        if not ap:
            logger.warning(f"apiprofile.rename: not_found (user_id={uid}, ap_id={ap_id})")
            return jsonify({"error": "not_found"}), 404
        ap.name = name or None
        db.commit()
        dt = (perf_counter() - t0) * 1000
        logger.info(f"apiprofile.rename: ok (user_id={uid}, ap_id={ap_id}, dt_ms={dt:.0f})")
        return jsonify({"ok": True})
    except Exception:
        logger.exception(f"apiprofile.rename: error (user_id={uid}, ap_id={ap_id})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.delete("/apiprofile/<int:ap_id>", endpoint="apiprofile_delete")
@auth_required
def delete_apiprofile(ap_id: int, db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    logger.info(f"apiprofile.delete: start (user_id={uid}, ap_id={ap_id})")
    try:
        ap = db.query(ApiProfile).filter(ApiProfile.id == ap_id, ApiProfile.user_id == uid).first()
        if not ap:
            logger.warning(f"apiprofile.delete: not_found (user_id={uid}, ap_id={ap_id})")
            return jsonify({"error": "not_found"}), 404
        cnt = (
            db.query(func.count(Account.id))
            .filter(Account.api_profile_id == ap.id, Account.user_id == uid)
            .scalar()
            or 0
        )
        if cnt > 0:
            logger.warning(
                f"apiprofile.delete: in_use (user_id={uid}, ap_id={ap_id}, accounts={cnt})"
            )
            return jsonify({"error": "api_profile_in_use", "accounts": int(cnt)}), 409
        db.delete(ap)
        db.commit()
        dt = (perf_counter() - t0) * 1000
        logger.info(f"apiprofile.delete: ok (user_id={uid}, ap_id={ap_id}, dt_ms={dt:.0f})")
        return jsonify({"ok": True})
    except Exception:
        logger.exception(f"apiprofile.delete: error (user_id={uid}, ap_id={ap_id})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/auth/send_code", endpoint="auth_send_code")
@auth_required
def send_code(db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    d = request.get_json(silent=True) or {}
    phone = (d.get("phone") or "").strip()
    api_profile_id = d.get("api_profile_id")

    norm = _norm_phone(phone)

    logger.info(
        f"auth.send_code: start (user_id={uid}, api_profile_id={api_profile_id}, "
        f"phone='{phone}', norm='{norm}')"
    )
    try:
        if not phone or not api_profile_id:
            logger.warning(f"auth.send_code: missing fields (user_id={uid})")
            return jsonify({"error": "phone_and_api_profile_id_required"}), 400

        exist = (
            db.query(Account.id, Account.phone)
            .filter(
                Account.user_id == uid,
                func.replace(func.replace(Account.phone, "+", ""), " ", "") == norm,
            )
            .first()
        )
        if exist:
            logger.warning(
                "auth.send_code: phone_exists (user_id=%s, acc_id=%s, phone_db='%s')",
                uid,
                exist.id,
                exist.phone,
            )
            return (
                jsonify(
                    {
                        "error": "phone_already_added",
                        "account_id": int(exist.id),
                        "phone": exist.phone,
                    }
                ),
                409,
            )

        res = _logins.start_login(db, user_id=uid, api_profile_id=int(api_profile_id), phone=norm)
        if "error" in res:
            logger.warning(f"auth.send_code: fail (user_id={uid}, error='{res.get('error')}')")
            return jsonify(res), int(res.get("http", 400))

        dt = (perf_counter() - t0) * 1000
        logger.info(f"auth.send_code: ok (user_id={uid}, dt_ms={dt:.0f})")
        return jsonify(res)
    except Exception:
        logger.exception(f"auth.send_code: error (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/auth/confirm_code", endpoint="auth_confirm_code")
@bp_acc.post("/auth/confirm_code", endpoint="auth_confirm_code")
@auth_required
def confirm_code(db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    d = request.get_json(silent=True) or {}
    login_id, code = d.get("login_id"), d.get("code")
    logger.info(f"auth.confirm_code: start (user_id={uid}, login_id={bool(login_id)})")
    try:
        if not login_id or not code:
            logger.warning(f"auth.confirm_code: missing fields (user_id={uid})")
            return jsonify({"error": "login_id_and_code_required"}), 400
        res = _logins.confirm_code(db, login_id, code)
        if "error" in res:
            logger.warning(f"auth.confirm_code: fail (user_id={uid}, error='{res.get('error')}')")
            return jsonify(res), int(res.get("http", 400))
        dt = (perf_counter() - t0) * 1000
        logger.info(f"auth.confirm_code: ok (user_id={uid}, dt_ms={dt:.0f})")
        return jsonify(res)
    except Exception:
        logger.exception(f"auth.confirm_code: error (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/auth/confirm_password", endpoint="auth_confirm_password")
@auth_required
def confirm_password(db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    d = request.get_json(silent=True) or {}
    login_id, password = d.get("login_id"), d.get("password")
    logger.info(f"auth.confirm_password: start (user_id={uid}, login_id={bool(login_id)})")
    try:
        if not login_id or not password:
            logger.warning(f"auth.confirm_password: missing fields (user_id={uid})")
            return jsonify({"error": "login_id_and_password_required"}), 400
        res = _logins.confirm_password(db, login_id, password)
        if "error" in res:
            logger.warning(
                f"auth.confirm_password: fail (user_id={uid}, error='{res.get('error')}')"
            )
            return jsonify(res), int(res.get("http", 400))
        dt = (perf_counter() - t0) * 1000
        logger.info(f"auth.confirm_password: ok (user_id={uid}, dt_ms={dt:.0f})")
        return jsonify(res)
    except Exception:
        logger.exception(f"auth.confirm_password: error (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/auth/cancel", endpoint="auth_cancel")
@auth_required
def cancel_login(db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    d = request.get_json(silent=True) or {}
    login_id = d.get("login_id")
    logger.info(f"auth.cancel: start (user_id={uid}, login_id={bool(login_id)})")
    try:
        if not login_id:
            logger.warning(f"auth.cancel: missing log_id (user_id={uid})")
            return jsonify({"error": "log_id_required"}), 400
        res = _logins.cancel(login_id)
        dt = (perf_counter() - t0) * 1000
        logger.info(f"auth.cancel: ok (user_id={uid}, dt_ms={dt:.0f})")
        return jsonify(res)
    except Exception:
        logger.exception(f"auth.cancel: error (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/account/<int:acc_id>/refresh", endpoint="account_refresh")
@auth_required
def account_refresh(acc_id: int, db: Session):
    t0 = perf_counter()
    uid = authed_request().user_id
    logger.info(f"account.refresh: start (user_id={uid}, acc_id={acc_id})")

    acc = db.query(Account).filter(Account.id == acc_id, Account.user_id == uid).first()
    if not acc:
        logger.warning(f"account.refresh: not_found (user_id={uid}, acc_id={acc_id})")
        return jsonify({"error": "not_found"}), 404

    ap = (
        db.query(ApiProfile.api_id, ApiProfile.api_hash)
        .filter(ApiProfile.id == acc.api_profile_id, ApiProfile.user_id == uid)
        .first()
    )
    if not ap:
        logger.warning(f"account.refresh: api_profile_missing (user_id={uid}, acc_id={acc_id})")
        return jsonify({"error": "api_profile_missing"}), 400

    def gen():
        db2 = SessionLocal()
        begin_user_refresh(uid)
        try:
            acc2 = db2.query(Account).filter(Account.id == acc_id, Account.user_id == uid).first()
            if not acc2:
                logger.warning(
                    f"account.refresh.stream: acc not_found (user_id={uid}, acc_id={acc_id})"
                )
                yield json.dumps({"error": "not_found"}, ensure_ascii=False) + "\n"
                return
            logger.debug(f"account.refresh.stream: begin (user_id={uid}, acc_id={acc_id})")
            for ev in iter_refresh_steps_core(
                db2, acc=acc2, api_id=ap.api_id, api_hash=ap.api_hash
            ):
                if ev.get("stage"):
                    logger.debug(
                        "account.refresh.stream: stage=%s (user_id=%s, acc_id=%s)",
                        ev["stage"],
                        uid,
                        acc_id,
                    )
                if ev.get("error"):
                    logger.warning(
                        "account.refresh.stream: error='%s' detail='%s' (user_id=%s, acc_id=%s)",
                        ev.get("error"),
                        ev.get("detail"),
                        uid,
                        acc_id,
                    )
                yield json.dumps(ev, ensure_ascii=False) + "\n"
            logger.debug(f"account.refresh.stream: end (user_id={uid}, acc_id={acc_id})")
        except Exception:
            logger.exception(f"account.refresh.stream: exception (user_id={uid}, acc_id={acc_id})")
            yield json.dumps({"error": "internal_error"}, ensure_ascii=False) + "\n"
        finally:
            try:
                db2.close()
            finally:
                end_user_refresh(uid)

    resp = Response(stream_with_context(gen()), mimetype="application/x-ndjson")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"

    dt = (perf_counter() - t0) * 1000
    logger.info(f"account.refresh: streaming (user_id={uid}, acc_id={acc_id}, dt_ms={dt:.0f})")
    return resp
