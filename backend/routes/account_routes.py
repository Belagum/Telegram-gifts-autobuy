import json
from time import perf_counter

from flask import Blueprint, request, jsonify, Response, stream_with_context
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import auth_required
from ..models import User, ApiProfile, Account
from ..services.accounts_service import any_stale, schedule_user_refresh, wait_until_ready, read_accounts, \
    end_user_refresh, iter_refresh_steps_core, begin_user_refresh
from ..pyro_login import PyroLoginManager
from ..db import SessionLocal
from ..logger import logger

bp_acc = Blueprint("accounts", __name__, url_prefix="/api")
_logins = PyroLoginManager()

def _mask_phone(p: str) -> str:
    p = (p or "").strip()
    return ("***" + p[-4:]) if len(p) >= 4 else "***"


@bp_acc.get("/accounts", endpoint="accounts_list")
@auth_required
def accounts(db:Session):
    t0=perf_counter(); uid=request.user_id
    wait=request.args.get("wait") in ("1","true","yes")
    logger.info("accounts.list: start (user_id=%s, wait=%s)", uid, wait)
    try:
        has_any=db.query(func.count(Account.id)).filter(Account.user_id==uid).scalar() or 0
        if not has_any:
            resp,code=jsonify({"state":"ready","accounts":[]}),200
        else:
            if any_stale(db, uid):
                schedule_user_refresh(uid)
                if wait and wait_until_ready(uid, timeout_sec=25.0):
                    accs=read_accounts(db, uid); resp,code=jsonify({"state":"ready","accounts":accs}),200
                else:
                    resp,code=jsonify({"state":"refreshing","accounts":None}),202
            else:
                accs=read_accounts(db, uid); resp,code=jsonify({"state":"ready","accounts":accs}),200
        resp.headers["Cache-Control"]="no-store"
        dt=(perf_counter()-t0)*1000
        logger.info("accounts.list: %s (user_id=%s, dt_ms=%.0f)", "ready" if code==200 else "refreshing", uid, dt)
        return resp,code
    except Exception:
        logger.exception("accounts.list: error (user_id=%s)", uid)
        return jsonify({"error":"internal_error"}),500


@bp_acc.get("/me", endpoint="me_info")
@auth_required
def me(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    logger.info("me: start (user_id={})", uid)
    try:
        u = db.get(User, uid)
        dt = (perf_counter() - t0) * 1000
        logger.info("me: ok (user_id={}, username='{}', dt_ms={:.0f})", uid, u.username, dt)
        return jsonify({"username": u.username})
    except Exception:
        logger.exception("me: error (user_id={})", uid)
        return jsonify({"error": "internal_error"}), 500


@bp_acc.get("/apiprofiles", endpoint="apiprofiles_list")
@auth_required
def list_api_profiles(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    logger.info("apiprofiles.list: start (user_id={})", uid)
    try:
        rows = db.query(ApiProfile).filter(ApiProfile.user_id == uid).order_by(ApiProfile.id.desc()).all()
        items = [{"id": r.id, "api_id": r.api_id, "name": r.name or ""} for r in rows]
        dt = (perf_counter() - t0) * 1000
        logger.info("apiprofiles.list: ok (user_id={}, count={}, dt_ms={:.0f})", uid, len(items), dt)
        return jsonify({"items": items})
    except Exception:
        logger.exception("apiprofiles.list: error (user_id={})", uid)
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/apiprofile", endpoint="apiprofile_create")
@auth_required
def create_apiprofile(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    d = request.get_json(silent=True) or {}
    api_id, api_hash = d.get("api_id"), d.get("api_hash")
    name = (d.get("name") or "").strip() or None
    logger.info("apiprofile.create: start (user_id={}, api_id={}, name='{}')", uid, api_id, name or "")
    try:
        if not api_id or not api_hash:
            logger.warning("apiprofile.create: missing fields (user_id={})", uid)
            return jsonify({"error": "api_id_and_api_hash_required"}), 400

        exist_id = db.query(ApiProfile).filter(
            ApiProfile.user_id == uid,
            ApiProfile.api_id == int(api_id)
        ).first()
        if exist_id:
            logger.warning("apiprofile.create: duplicate api_id (user_id={}, existing_id={})", uid, exist_id.id)
            return jsonify({"error": "duplicate_api_id", "existing_id": exist_id.id}), 409

        exist_hash = db.query(ApiProfile).filter(
            ApiProfile.user_id == uid,
            ApiProfile.api_hash == str(api_hash)
        ).first()
        if exist_hash:
            logger.warning("apiprofile.create: duplicate api_hash (user_id={}, existing_id={})", uid, exist_hash.id)
            return jsonify({"error": "duplicate_api_hash", "existing_id": exist_hash.id}), 409

        ap = ApiProfile(user_id=uid, api_id=int(api_id), api_hash=str(api_hash), name=name)
        db.add(ap); db.commit()

        dt = (perf_counter() - t0) * 1000
        logger.info("apiprofile.create: ok (user_id={}, id={}, dt_ms={:.0f})", uid, ap.id, dt)
        return jsonify({"api_profile_id": ap.id})
    except Exception:
        logger.exception("apiprofile.create: error (user_id={})", uid)
        return jsonify({"error": "internal_error"}), 500


@bp_acc.patch("/apiprofile/<int:ap_id>", endpoint="apiprofile_rename")
@auth_required
def rename_apiprofile(ap_id: int, db: Session):
    t0 = perf_counter()
    uid = request.user_id
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    logger.info("apiprofile.rename: start (user_id={}, ap_id={}, name='{}')", uid, ap_id, name)
    try:
        ap = db.query(ApiProfile).filter(ApiProfile.id == ap_id, ApiProfile.user_id == uid).first()
        if not ap:
            logger.warning("apiprofile.rename: not_found (user_id={}, ap_id={})", uid, ap_id)
            return jsonify({"error": "not_found"}), 404
        ap.name = name or None
        db.commit()
        dt = (perf_counter() - t0) * 1000
        logger.info("apiprofile.rename: ok (user_id={}, ap_id={}, dt_ms={:.0f})", uid, ap_id, dt)
        return jsonify({"ok": True})
    except Exception:
        logger.exception("apiprofile.rename: error (user_id={}, ap_id={})", uid, ap_id)
        return jsonify({"error": "internal_error"}), 500


@bp_acc.delete("/apiprofile/<int:ap_id>", endpoint="apiprofile_delete")
@auth_required
def delete_apiprofile(ap_id: int, db: Session):
    t0 = perf_counter()
    uid = request.user_id
    logger.info("apiprofile.delete: start (user_id={}, ap_id={})", uid, ap_id)
    try:
        ap = db.query(ApiProfile).filter(ApiProfile.id == ap_id, ApiProfile.user_id == uid).first()
        if not ap:
            logger.warning("apiprofile.delete: not_found (user_id={}, ap_id={})", uid, ap_id)
            return jsonify({"error": "not_found"}), 404
        cnt = db.query(func.count(Account.id)).filter(
            Account.api_profile_id == ap.id, Account.user_id == uid
        ).scalar() or 0
        if cnt > 0:
            logger.warning("apiprofile.delete: in_use (user_id={}, ap_id={}, accounts={})", uid, ap_id, cnt)
            return jsonify({"error": "api_profile_in_use", "accounts": int(cnt)}), 409
        db.delete(ap); db.commit()
        dt = (perf_counter() - t0) * 1000
        logger.info("apiprofile.delete: ok (user_id={}, ap_id={}, dt_ms={:.0f})", uid, ap_id, dt)
        return jsonify({"ok": True})
    except Exception:
        logger.exception("apiprofile.delete: error (user_id={}, ap_id={})", uid, ap_id)
        return jsonify({"error": "internal_error"}), 500

def _norm_phone(p: str) -> str:
    return (p or "").replace("+", "").replace(" ", "")

@bp_acc.post("/auth/send_code", endpoint="auth_send_code")
@auth_required
def send_code(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    d = request.get_json(silent=True) or {}
    phone = (d.get("phone") or "").strip()
    api_profile_id = d.get("api_profile_id")
    logger.info("auth.send_code: start (user_id={}, api_profile_id={}, phone='{}')", uid, api_profile_id, _mask_phone(phone))
    try:
        if not phone or not api_profile_id:
            logger.warning("auth.send_code: missing fields (user_id={})", uid)
            return jsonify({"error": "phone_and_api_profile_id_required"}), 400

        norm = _norm_phone(phone)
        exist = db.query(Account.id, Account.phone).filter(
            Account.user_id == uid,
            func.replace(func.replace(Account.phone, "+", ""), " ", "") == norm
        ).first()
        if exist:
            logger.warning("auth.send_code: phone_exists (user_id={}, acc_id={}, phone_db='{}')", uid, exist.id, exist.phone)
            return jsonify({
                "error": "phone_already_added",
                "account_id": int(exist.id),
                "phone": exist.phone
            }), 409

        res = _logins.start_login(db, user_id=uid, api_profile_id=int(api_profile_id), phone=phone)
        if "error" in res:
            logger.warning("auth.send_code: fail (user_id={}, error='{}')", uid, res.get("error"))
            return jsonify(res), int(res.get("http", 400))

        dt = (perf_counter() - t0) * 1000
        logger.info("auth.send_code: ok (user_id={}, dt_ms={:.0f})", uid, dt)
        return jsonify(res)
    except Exception:
        logger.exception("auth.send_code: error (user_id={})", uid)
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/auth/confirm_code", endpoint="auth_confirm_code")
@auth_required
def confirm_code(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    d = request.get_json(silent=True) or {}
    login_id, code = d.get("login_id"), d.get("code")
    logger.info("auth.confirm_code: start (user_id={}, login_id={})", uid, bool(login_id))
    try:
        if not login_id or not code:
            logger.warning("auth.confirm_code: missing fields (user_id={})", uid)
            return jsonify({"error": "login_id_and_code_required"}), 400
        res = _logins.confirm_code(db, login_id, code)
        if "error" in res:
            logger.warning("auth.confirm_code: fail (user_id={}, error='{}')", uid, res.get("error"))
            return jsonify(res), int(res.get("http", 400))
        dt = (perf_counter() - t0) * 1000
        logger.info("auth.confirm_code: ok (user_id={}, dt_ms={:.0f})", uid, dt)
        return jsonify(res)
    except Exception:
        logger.exception("auth.confirm_code: error (user_id={})", uid)
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/auth/confirm_password", endpoint="auth_confirm_password")
@auth_required
def confirm_password(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    d = request.get_json(silent=True) or {}
    login_id, password = d.get("login_id"), d.get("password")
    logger.info("auth.confirm_password: start (user_id={}, login_id={})", uid, bool(login_id))
    try:
        if not login_id or not password:
            logger.warning("auth.confirm_password: missing fields (user_id={})", uid)
            return jsonify({"error": "login_id_and_password_required"}), 400
        res = _logins.confirm_password(db, login_id, password)
        if "error" in res:
            logger.warning("auth.confirm_password: fail (user_id={}, error='{}')", uid, res.get("error"))
            return jsonify(res), int(res.get("http", 400))
        dt = (perf_counter() - t0) * 1000
        logger.info("auth.confirm_password: ok (user_id={}, dt_ms={:.0f})", uid, dt)
        return jsonify(res)
    except Exception:
        logger.exception("auth.confirm_password: error (user_id={})", uid)
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/auth/cancel", endpoint="auth_cancel")
@auth_required
def cancel_login(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    d = request.get_json(silent=True) or {}
    login_id = d.get("login_id")
    logger.info("auth.cancel: start (user_id={}, login_id={})", uid, bool(login_id))
    try:
        if not login_id:
            logger.warning("auth.cancel: missing log_id (user_id={})", uid)
            return jsonify({"error": "log_id_required"}), 400
        res = _logins.cancel(login_id)
        dt = (perf_counter() - t0) * 1000
        logger.info("auth.cancel: ok (user_id={}, dt_ms={:.0f})", uid, dt)
        return jsonify(res)
    except Exception:
        logger.exception("auth.cancel: error (user_id={})", uid)
        return jsonify({"error": "internal_error"}), 500


@bp_acc.post("/account/<int:acc_id>/refresh", endpoint="account_refresh")
@auth_required
def account_refresh(acc_id: int, db: Session):
    t0 = perf_counter()
    uid = request.user_id
    logger.info("account.refresh: start (user_id=%s, acc_id=%s)", uid, acc_id)

    acc = db.query(Account).filter(Account.id == acc_id, Account.user_id == uid).first()
    if not acc:
        logger.warning("account.refresh: not_found (user_id=%s, acc_id=%s)", uid, acc_id)
        return jsonify({"error": "not_found"}), 404

    ap = db.query(ApiProfile.api_id, ApiProfile.api_hash).filter(
        ApiProfile.id == acc.api_profile_id,
        ApiProfile.user_id == uid
    ).first()
    if not ap:
        logger.warning("account.refresh: api_profile_missing (user_id=%s, acc_id=%s)", uid, acc_id)
        return jsonify({"error": "api_profile_missing"}), 400

    def gen():
        db2 = SessionLocal()
        begin_user_refresh(uid)
        try:
            acc2 = db2.query(Account).filter(Account.id == acc_id, Account.user_id == uid).first()
            if not acc2:
                logger.warning("account.refresh.stream: acc not_found (user_id=%s, acc_id=%s)", uid, acc_id)
                yield json.dumps({"error": "not_found"}, ensure_ascii=False) + "\n"
                return
            logger.debug("account.refresh.stream: begin (user_id=%s, acc_id=%s)", uid, acc_id)
            for ev in iter_refresh_steps_core(db2, acc=acc2, api_id=ap.api_id, api_hash=ap.api_hash):
                if ev.get("stage"):
                    logger.debug("account.refresh.stream: stage=%s (user_id=%s, acc_id=%s)", ev["stage"], uid, acc_id)
                if ev.get("error"):
                    logger.warning("account.refresh.stream: error='%s' detail='%s' (user_id=%s, acc_id=%s)",
                                   ev.get("error"), ev.get("detail"), uid, acc_id)
                yield json.dumps(ev, ensure_ascii=False) + "\n"
            logger.debug("account.refresh.stream: end (user_id=%s, acc_id=%s)", uid, acc_id)
        except Exception:
            logger.exception("account.refresh.stream: exception (user_id=%s, acc_id=%s)", uid, acc_id)
            yield json.dumps({"error": "internal_error"}, ensure_ascii=False) + "\n"
        finally:
            try: db2.close()
            finally: end_user_refresh(uid)

    resp = Response(stream_with_context(gen()), mimetype="application/x-ndjson")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"

    dt = (perf_counter() - t0) * 1000
    logger.info("account.refresh: streaming (user_id=%s, acc_id=%s, dt_ms=%.0f)", uid, acc_id, dt)
    return resp