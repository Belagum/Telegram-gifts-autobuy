# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""HTTP controller for application settings endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session

from backend.auth import auth_required, authed_request
from backend.services.settings_service import read_user_settings, set_user_settings


class SettingsController:
    """Controller exposing user settings operations."""

    def as_blueprint(self) -> Blueprint:
        bp = Blueprint("settings", __name__, url_prefix="/api")
        bp.add_url_rule(
            "/settings", view_func=self.get_settings, methods=["GET"], endpoint="settings_get"
        )
        bp.add_url_rule(
            "/settings",
            view_func=self.update_settings,
            methods=["POST"],
            endpoint="settings_set",
        )
        return bp

    @auth_required
    def get_settings(self, _db: Session):
        return jsonify(read_user_settings(authed_request().user_id))

    @auth_required
    def update_settings(self, _db: Session):
        payload = request.get_json(silent=True) or {}
        token = payload.get("bot_token")
        chat = payload.get("notify_chat_id")
        target = payload.get("buy_target_id")
        fallback = payload.get("buy_target_on_fail_only")
        if token is not None and not isinstance(token, str):
            return jsonify({"error": "bot_token_type"}), 400
        if chat is not None and not isinstance(chat, (str, int)):
            return jsonify({"error": "notify_chat_id_type"}), 400
        if target is not None and not isinstance(target, (str, int)):
            return jsonify({"error": "buy_target_id_type"}), 400
        if fallback is not None and not isinstance(fallback, bool):
            return jsonify({"error": "buy_target_on_fail_only_type"}), 400
        try:
            user_id = authed_request().user_id
            settings = set_user_settings(
                user_id, (token or "").strip() or None, chat, target, fallback
            )
        except ValueError as exc:
            message = str(exc)
            if "channel" in message or "100" in message:
                return jsonify({"error": "notify_chat_id_invalid"}), 400
            return jsonify({"error": "buy_target_id_invalid"}), 400
        return jsonify({"ok": True, "settings": settings})
