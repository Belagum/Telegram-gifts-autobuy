# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from flask import Blueprint, jsonify

from backend.infrastructure.health import check_database


class MiscController:
    def as_blueprint(self) -> Blueprint:
        bp = Blueprint("misc", __name__)
        bp.add_url_rule("/api/health", view_func=self.health, methods=["GET"])
        return bp

    def health(self):
        status: dict[str, object] = {"ok": True}
        try:
            check_database()
            status["database"] = "ok"
        except Exception as exc:  # pragma: no cover
            status["ok"] = False
            status["database"] = f"error: {exc}"
        return jsonify(status)
