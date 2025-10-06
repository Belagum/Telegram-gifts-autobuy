# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session

from ..auth import auth_required, authed_request
from ..services.settings_service import read_user_settings, set_user_settings

bp_settings = Blueprint("settings", __name__, url_prefix="/api")


@bp_settings.get("/settings", endpoint="settings_get")
@auth_required
def settings_get(db: Session):
    return jsonify(read_user_settings(authed_request().user_id))


@bp_settings.post("/settings", endpoint="settings_set")
@auth_required
def settings_set(db: Session):
    d = request.get_json(silent=True) or {}
    token = d.get("bot_token")
    chat = d.get("notify_chat_id")
    target = d.get("buy_target_id")
    if token is not None and not isinstance(token, str):
        return jsonify({"error": "bot_token_type"}), 400
    if chat is not None and not isinstance(chat, (str, int)):
        return jsonify({"error": "notify_chat_id_type"}), 400
    if target is not None and not isinstance(target, (str, int)):
        return jsonify({"error": "buy_target_id_type"}), 400
    try:
        uid = authed_request().user_id
        out = set_user_settings(uid, (token or "").strip() or None, chat, target)
    except ValueError as e:
        msg = str(e)
        if "channel" in msg or "100" in msg:
            return jsonify({"error": "notify_chat_id_invalid"}), 400
        return jsonify({"error": "buy_target_id_invalid"}), 400
    return jsonify({"ok": True, "settings": out})
