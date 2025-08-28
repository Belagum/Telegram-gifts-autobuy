# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session

from ..auth import auth_required
from ..services.settings_service import read_user_settings, set_user_settings

bp_settings = Blueprint("settings", __name__, url_prefix="/api")

@bp_settings.get("/settings", endpoint="settings_get")
@auth_required
def settings_get(db: Session):
    return jsonify(read_user_settings(request.user_id))

@bp_settings.post("/settings", endpoint="settings_set")
@auth_required
def settings_set(db: Session):
    d = request.get_json(silent=True) or {}
    token = d.get("bot_token")
    if token is not None and not isinstance(token, str):
        return jsonify({"error":"bot_token_type"}), 400
    out = set_user_settings(request.user_id, (token or "").strip() or None)
    return jsonify({"ok": True, "settings": out})
