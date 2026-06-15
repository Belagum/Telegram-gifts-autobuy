# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from flask import Blueprint, jsonify

from backend.infrastructure.health import check_database
from backend.shared.logging import logger


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
        except Exception:  # pragma: no cover
            logger.exception("health: database check failed")
            status["ok"] = False
            status["database"] = "error"
        return jsonify(status)
