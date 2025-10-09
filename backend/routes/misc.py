# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Miscellaneous health endpoints."""

from backend.infrastructure.health import check_database
from flask import Blueprint, jsonify

bp_misc = Blueprint("misc", __name__)


@bp_misc.get("/api/health")
def health():
    status: dict[str, object] = {"ok": True}
    try:
        check_database()
        status["database"] = "ok"
    except Exception as exc:  # pragma: no cover
        status["ok"] = False
        status["database"] = f"error: {exc}"
    return jsonify(status)
