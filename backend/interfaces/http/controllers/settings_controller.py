# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session

from backend.infrastructure.auth import auth_required, authed_request
from backend.services.settings_service import read_user_settings, set_user_settings
from backend.shared.errors import (
    InfrastructureError,
    InvalidBotTokenError,
    InvalidBuyTargetIdError,
    InvalidChatIdError,
    InvalidFallbackError,
    InvalidNotifyChatIdError,
    InvalidTargetIdError,
)
from backend.shared.middleware.csrf import csrf_protect


class SettingsController:

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
    @csrf_protect
    def update_settings(self, _db: Session):
        payload = request.get_json(silent=True) or {}
        token = payload.get("bot_token")
        chat = payload.get("notify_chat_id")
        target = payload.get("buy_target_id")
        fallback = payload.get("buy_target_on_fail_only")
        
        if token is not None and not isinstance(token, str):
            raise InvalidBotTokenError()
        if chat is not None and not isinstance(chat, (str, int)):
            raise InvalidChatIdError()
        if target is not None and not isinstance(target, (str, int)):
            raise InvalidTargetIdError()
        if fallback is not None and not isinstance(fallback, bool):
            raise InvalidFallbackError()
            
        try:
            user_id = authed_request().user_id
            settings = set_user_settings(
                user_id, (token or "").strip() or None, chat, target, fallback
            )
        except ValueError as exc:
            message = str(exc)
            if "channel" in message or "100" in message:
                raise InvalidNotifyChatIdError()
            raise InvalidBuyTargetIdError()
        except Exception as exc:
            raise InfrastructureError(f"Failed to update settings: {exc}") from exc
            
        return jsonify({"ok": True, "settings": settings})
