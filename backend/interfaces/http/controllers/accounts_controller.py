# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""HTTP controller for account-related endpoints."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from time import perf_counter

from flask import Blueprint, Response, jsonify, request, stream_with_context
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth import auth_required, authed_request
from backend.infrastructure.db import SessionLocal
from backend.infrastructure.db.models import Account, ApiProfile, User
from backend.pyro_login import PyroLoginManager
from backend.services.accounts_service import (
    any_stale,
    begin_user_refresh,
    end_user_refresh,
    iter_refresh_steps_core,
    read_accounts,
    schedule_user_refresh,
    wait_until_ready,
)
from backend.shared.logging import logger


class AccountsController:
    """Controller exposing account management endpoints."""

    def __init__(self, *, login_manager: PyroLoginManager | None = None) -> None:
        self._login_manager = login_manager or PyroLoginManager()

    def as_blueprint(self) -> Blueprint:
        bp = Blueprint("accounts", __name__, url_prefix="/api")

        bp.add_url_rule(
            "/accounts", view_func=self.list_accounts, methods=["GET"], endpoint="accounts_list"
        )
        bp.add_url_rule("/me", view_func=self.current_user, methods=["GET"], endpoint="me_info")
        bp.add_url_rule(
            "/apiprofiles",
            view_func=self.list_api_profiles,
            methods=["GET"],
            endpoint="apiprofiles_list",
        )
        bp.add_url_rule(
            "/apiprofile",
            view_func=self.create_api_profile,
            methods=["POST"],
            endpoint="apiprofile_create",
        )
        bp.add_url_rule(
            "/apiprofile/<int:api_profile_id>",
            view_func=self.rename_api_profile,
            methods=["PATCH"],
            endpoint="apiprofile_rename",
        )
        bp.add_url_rule(
            "/apiprofile/<int:api_profile_id>",
            view_func=self.delete_api_profile,
            methods=["DELETE"],
            endpoint="apiprofile_delete",
        )
        bp.add_url_rule(
            "/auth/send_code",
            view_func=self.send_code,
            methods=["POST"],
            endpoint="auth_send_code",
        )
        bp.add_url_rule(
            "/auth/confirm_code",
            view_func=self.confirm_code,
            methods=["POST"],
            endpoint="auth_confirm_code",
        )
        bp.add_url_rule(
            "/auth/confirm_password",
            view_func=self.confirm_password,
            methods=["POST"],
            endpoint="auth_confirm_password",
        )
        bp.add_url_rule(
            "/auth/cancel",
            view_func=self.cancel_login,
            methods=["POST"],
            endpoint="auth_cancel",
        )
        bp.add_url_rule(
            "/account/<int:account_id>/refresh",
            view_func=self.refresh_account,
            methods=["POST"],
            endpoint="account_refresh",
        )

        return bp

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        digits = re.sub(r"\D", "", phone or "")
        if not digits:
            return ""
        if digits.startswith("8") and len(digits) == 11:
            digits = "7" + digits[1:]
        return "+" + digits

    @auth_required
    def list_accounts(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        wait = request.args.get("wait") in ("1", "true", "yes")
        logger.info(f"accounts.list: start (user_id={user_id}, wait={wait})")
        try:
            has_any = (
                db.query(func.count(Account.id)).filter(Account.user_id == user_id).scalar() or 0
            )
            if not has_any:
                response, code = jsonify({"state": "ready", "accounts": []}), 200
            else:
                if any_stale(db, user_id):
                    schedule_user_refresh(user_id)
                    if wait and wait_until_ready(user_id, timeout_sec=25.0):
                        accounts = read_accounts(db, user_id)
                        response, code = jsonify({"state": "ready", "accounts": accounts}), 200
                    else:
                        response, code = jsonify({"state": "refreshing", "accounts": None}), 202
                else:
                    accounts = read_accounts(db, user_id)
                    response, code = jsonify({"state": "ready", "accounts": accounts}), 200
            response.headers["Cache-Control"] = "no-store"
            dt = (perf_counter() - t0) * 1000
            status = "ready" if code == 200 else "refreshing"
            logger.info(f"accounts.list: {status} (user_id={user_id}, dt_ms={dt:.0f})")
            return response, code
        except Exception:
            logger.exception(f"accounts.list: error (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def current_user(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        logger.info(f"me: start (user_id={user_id})")
        try:
            user = db.get(User, user_id)
            if not user:
                logger.warning(f"me: user_not_found (user_id={user_id})")
                return jsonify({"error": "not_found"}), 404
            dt = (perf_counter() - t0) * 1000
            logger.info(f"me: ok (user_id={user_id}, username='{user.username}', dt_ms={dt:.0f})")
            return jsonify({"username": user.username})
        except Exception:
            logger.exception(f"me: error (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def list_api_profiles(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        logger.info(f"apiprofiles.list: start (user_id={user_id})")
        try:
            rows = (
                db.query(ApiProfile)
                .filter(ApiProfile.user_id == user_id)
                .order_by(ApiProfile.id.desc())
                .all()
            )
            items = [{"id": row.id, "api_id": row.api_id, "name": row.name or ""} for row in rows]
            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"apiprofiles.list: ok (user_id={user_id}, count={len(items)}, dt_ms={dt:.0f})"
            )
            return jsonify({"items": items})
        except Exception:
            logger.exception(f"apiprofiles.list: error (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def create_api_profile(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        api_id, api_hash = payload.get("api_id"), payload.get("api_hash")
        name = (payload.get("name") or "").strip() or None
        logger.info(
            f"apiprofile.create: start (user_id={user_id}, api_id={api_id}, name='{name or ''}')"
        )
        try:
            if not api_id or not api_hash:
                logger.warning(f"apiprofile.create: missing fields (user_id={user_id})")
                return jsonify({"error": "api_id_and_api_hash_required"}), 400

            existing_by_id = (
                db.query(ApiProfile)
                .filter(ApiProfile.user_id == user_id, ApiProfile.api_id == int(api_id))
                .first()
            )
            if existing_by_id:
                logger.warning(
                    "apiprofile.create: duplicate api_id "
                    f"(user_id={user_id}, existing_id={existing_by_id.id})"
                )
                return (
                    jsonify({"error": "duplicate_api_id", "existing_id": existing_by_id.id}),
                    409,
                )

            existing_by_hash = (
                db.query(ApiProfile)
                .filter(ApiProfile.user_id == user_id, ApiProfile.api_hash == str(api_hash))
                .first()
            )
            if existing_by_hash:
                logger.warning(
                    "apiprofile.create: duplicate api_hash "
                    f"(user_id={user_id}, existing_id={existing_by_hash.id})"
                )
                return (
                    jsonify({"error": "duplicate_api_hash", "existing_id": existing_by_hash.id}),
                    409,
                )

            api_profile = ApiProfile(
                user_id=user_id, api_id=int(api_id), api_hash=str(api_hash), name=name
            )
            db.add(api_profile)
            db.commit()

            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"apiprofile.create: ok (user_id={user_id}, id={api_profile.id}, dt_ms={dt:.0f})"
            )
            return jsonify({"api_profile_id": api_profile.id})
        except Exception:
            logger.exception(f"apiprofile.create: error (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def rename_api_profile(self, api_profile_id: int, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        logger.info(
            f"apiprofile.rename: start (user_id={user_id}, ap_id={api_profile_id}, name='{name}')"
        )
        try:
            api_profile = (
                db.query(ApiProfile)
                .filter(ApiProfile.id == api_profile_id, ApiProfile.user_id == user_id)
                .first()
            )
            if not api_profile:
                logger.warning(
                    f"apiprofile.rename: not_found (user_id={user_id}, ap_id={api_profile_id})"
                )
                return jsonify({"error": "not_found"}), 404
            api_profile.name = name or None
            db.commit()
            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"apiprofile.rename: ok (user_id={user_id}, ap_id={api_profile_id}, dt_ms={dt:.0f})"
            )
            return jsonify({"ok": True})
        except Exception:
            logger.exception(
                f"apiprofile.rename: error (user_id={user_id}, ap_id={api_profile_id})"
            )
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def delete_api_profile(self, api_profile_id: int, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        logger.info(f"apiprofile.delete: start (user_id={user_id}, ap_id={api_profile_id})")
        try:
            api_profile = (
                db.query(ApiProfile)
                .filter(ApiProfile.id == api_profile_id, ApiProfile.user_id == user_id)
                .first()
            )
            if not api_profile:
                logger.warning(
                    f"apiprofile.delete: not_found (user_id={user_id}, ap_id={api_profile_id})"
                )
                return jsonify({"error": "not_found"}), 404
            count = (
                db.query(func.count(Account.id))
                .filter(Account.api_profile_id == api_profile.id, Account.user_id == user_id)
                .scalar()
                or 0
            )
            if count > 0:
                logger.warning(
                    "apiprofile.delete: in_use "
                    f"(user_id={user_id}, ap_id={api_profile_id}, accounts={count})"
                )
                return (
                    jsonify({"error": "api_profile_in_use", "accounts": int(count)}),
                    409,
                )
            db.delete(api_profile)
            db.commit()
            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"apiprofile.delete: ok (user_id={user_id}, ap_id={api_profile_id}, dt_ms={dt:.0f})"
            )
            return jsonify({"ok": True})
        except Exception:
            logger.exception(
                f"apiprofile.delete: error (user_id={user_id}, ap_id={api_profile_id})"
            )
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def send_code(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        phone = (payload.get("phone") or "").strip()
        api_profile_id = payload.get("api_profile_id")
        normalized_phone = self._normalize_phone(phone)
        logger.info(
            "auth.send_code: start (user_id=%s, api_profile_id=%s, phone='%s', norm='%s')",
            user_id,
            api_profile_id,
            phone,
            normalized_phone,
        )
        try:
            if not phone or not api_profile_id:
                logger.warning(f"auth.send_code: missing fields (user_id={user_id})")
                return jsonify({"error": "phone_and_api_profile_id_required"}), 400

            existing = (
                db.query(Account.id, Account.phone)
                .filter(
                    Account.user_id == user_id,
                    func.replace(func.replace(Account.phone, "+", ""), " ", "") == normalized_phone,
                )
                .first()
            )
            if existing:
                logger.warning(
                    "auth.send_code: phone_exists (user_id=%s, acc_id=%s, phone_db='%s')",
                    user_id,
                    existing.id,
                    existing.phone,
                )
                return (
                    jsonify(
                        {
                            "error": "phone_already_added",
                            "account_id": int(existing.id),
                            "phone": existing.phone,
                        }
                    ),
                    409,
                )

            result = self._login_manager.start_login(
                db,
                user_id=user_id,
                api_profile_id=int(api_profile_id),
                phone=normalized_phone,
            )
            if "error" in result:
                logger.warning(
                    "auth.send_code: fail (user_id=%s, error='%s')",
                    user_id,
                    result.get("error"),
                )
                return jsonify(result), int(result.get("http", 400))

            dt = (perf_counter() - t0) * 1000
            logger.info(f"auth.send_code: ok (user_id={user_id}, dt_ms={dt:.0f})")
            return jsonify(result)
        except Exception:
            logger.exception(f"auth.send_code: error (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def confirm_code(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        login_id, code = payload.get("login_id"), payload.get("code")
        logger.info(f"auth.confirm_code: start (user_id={user_id}, login_id={bool(login_id)})")
        try:
            if not login_id or not code:
                logger.warning(f"auth.confirm_code: missing fields (user_id={user_id})")
                return jsonify({"error": "login_id_and_code_required"}), 400
            result = self._login_manager.confirm_code(db, login_id, code)
            if "error" in result:
                logger.warning(
                    "auth.confirm_code: fail (user_id=%s, error='%s')",
                    user_id,
                    result.get("error"),
                )
                return jsonify(result), int(result.get("http", 400))
            dt = (perf_counter() - t0) * 1000
            logger.info(f"auth.confirm_code: ok (user_id={user_id}, dt_ms={dt:.0f})")
            return jsonify(result)
        except Exception:
            logger.exception(f"auth.confirm_code: error (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def confirm_password(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        login_id, password = payload.get("login_id"), payload.get("password")
        logger.info(f"auth.confirm_password: start (user_id={user_id}, login_id={bool(login_id)})")
        try:
            if not login_id or not password:
                logger.warning(f"auth.confirm_password: missing fields (user_id={user_id})")
                return jsonify({"error": "login_id_and_password_required"}), 400
            result = self._login_manager.confirm_password(db, login_id, password)
            if "error" in result:
                logger.warning(
                    "auth.confirm_password: fail (user_id=%s, error='%s')",
                    user_id,
                    result.get("error"),
                )
                return jsonify(result), int(result.get("http", 400))
            dt = (perf_counter() - t0) * 1000
            logger.info(f"auth.confirm_password: ok (user_id={user_id}, dt_ms={dt:.0f})")
            return jsonify(result)
        except Exception:
            logger.exception(f"auth.confirm_password: error (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def cancel_login(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        login_id = payload.get("login_id")
        logger.info(f"auth.cancel: start (user_id={user_id}, login_id={bool(login_id)})")
        try:
            if not login_id:
                logger.warning(f"auth.cancel: missing log_id (user_id={user_id})")
                return jsonify({"error": "log_id_required"}), 400
            result = self._login_manager.cancel(login_id)
            dt = (perf_counter() - t0) * 1000
            logger.info(f"auth.cancel: ok (user_id={user_id}, dt_ms={dt:.0f})")
            return jsonify(result)
        except Exception:
            logger.exception(f"auth.cancel: error (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def refresh_account(self, account_id: int, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        logger.info(f"account.refresh: start (user_id={user_id}, acc_id={account_id})")

        account = (
            db.query(Account).filter(Account.id == account_id, Account.user_id == user_id).first()
        )
        if not account:
            logger.warning(f"account.refresh: not_found (user_id={user_id}, acc_id={account_id})")
            return jsonify({"error": "not_found"}), 404

        api_profile = (
            db.query(ApiProfile.api_id, ApiProfile.api_hash)
            .filter(ApiProfile.id == account.api_profile_id, ApiProfile.user_id == user_id)
            .first()
        )
        if not api_profile:
            logger.warning(
                f"account.refresh: api_profile_missing (user_id={user_id}, acc_id={account_id})"
            )
            return jsonify({"error": "api_profile_missing"}), 400

        def stream() -> Iterator[str]:
            db2 = SessionLocal()
            begin_user_refresh(user_id)
            try:
                account_copy = (
                    db2.query(Account)
                    .filter(Account.id == account_id, Account.user_id == user_id)
                    .first()
                )
                if not account_copy:
                    logger.warning(
                        "account.refresh.stream: acc not_found (user_id=%s, acc_id=%s)",
                        user_id,
                        account_id,
                    )
                    yield json.dumps({"error": "not_found"}, ensure_ascii=False) + "\n"
                    return
                logger.debug(
                    f"account.refresh.stream: begin (user_id={user_id}, acc_id={account_id})"
                )
                for event in iter_refresh_steps_core(
                    db2, acc=account_copy, api_id=api_profile.api_id, api_hash=api_profile.api_hash
                ):
                    if event.get("stage"):
                        logger.debug(
                            "account.refresh.stream: stage=%s (user_id=%s, acc_id=%s)",
                            event["stage"],
                            user_id,
                            account_id,
                        )
                    if event.get("error"):
                        logger.warning(
                            "account.refresh.stream: error='%s' detail='%s' user_id=%s acc_id=%s",
                            event.get("error"),
                            event.get("detail"),
                            user_id,
                            account_id,
                        )
                    yield json.dumps(event, ensure_ascii=False) + "\n"
                logger.debug(
                    f"account.refresh.stream: end (user_id={user_id}, acc_id={account_id})"
                )
            except Exception:
                logger.exception(
                    f"account.refresh.stream: exception (user_id={user_id}, acc_id={account_id})"
                )
                yield json.dumps({"error": "internal_error"}, ensure_ascii=False) + "\n"
            finally:
                try:
                    db2.close()
                finally:
                    end_user_refresh(user_id)

        generator = stream_with_context(stream())
        response = Response(generator, mimetype="application/x-ndjson")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"

        dt = (perf_counter() - t0) * 1000
        logger.info(
            f"account.refresh: streaming (user_id={user_id}, acc_id={account_id}, dt_ms={dt:.0f})"
        )
        return response
