# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""HTTP controller for channel management endpoints."""

from __future__ import annotations

from time import perf_counter

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session

from backend.auth import auth_required, authed_request
from backend.services.channels_service import (
    create_channel,
    delete_channel,
    list_channels,
    update_channel,
)
from backend.shared.logging import logger


class ChannelsController:
    """Controller exposing channel CRUD endpoints."""

    def as_blueprint(self) -> Blueprint:
        bp = Blueprint("channels", __name__, url_prefix="/api")
        bp.add_url_rule("/channels", view_func=self.list_channels, methods=["GET"])
        bp.add_url_rule("/channel", view_func=self.create, methods=["POST"])
        bp.add_url_rule(
            "/channel/<int:channel_id>",
            view_func=self.update,
            methods=["PATCH"],
        )
        bp.add_url_rule(
            "/channel/<int:channel_id>",
            view_func=self.delete,
            methods=["DELETE"],
        )
        return bp

    @auth_required
    def list_channels(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        try:
            items = list_channels(db, user_id)
            dt = (perf_counter() - t0) * 1000
            logger.info(f"channels.list: ok (user_id={user_id}, n={len(items)}, dt_ms={dt:.0f})")
            return jsonify({"items": items})
        except Exception:
            logger.exception(f"channels.list: err (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def create(self, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        try:
            result = create_channel(
                db,
                user_id,
                payload.get("channel_id"),
                payload.get("price_min"),
                payload.get("price_max"),
                payload.get("supply_min"),
                payload.get("supply_max"),
                (payload.get("title") or "").strip() or None,
            )
            if "error" in result:
                code = 409 if result["error"] == "duplicate_channel" else 400
                logger.info(
                    "channel.create: fail (user_id=%s, err=%s, detail=%s)",
                    user_id,
                    result.get("error"),
                    result.get("detail", ""),
                )
                return jsonify(result), code

            dt = (perf_counter() - t0) * 1000
            logger.info(
                "channel.create: ok (user_id=%s, channel_row_id=%s, dt_ms=%.0f)",
                user_id,
                result["channel_id"],
                dt,
            )
            return jsonify(result)
        except ValueError as exc:
            logger.info(f"channel.create: bad_channel_id (user_id={user_id}, detail={exc})")
            return jsonify({"error": "bad_channel_id", "detail": str(exc)}), 400
        except Exception:
            logger.exception(f"channel.create: err (user_id={user_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def update(self, channel_id: int, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        try:
            result = update_channel(db, user_id, channel_id, **payload)
            if "error" in result:
                logger.info(f"channel.update: not_found (user_id={user_id}, ch_id={channel_id})")
                return jsonify(result), 404

            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"channel.update: ok (user_id={user_id}, ch_id={channel_id}, dt_ms={dt:.0f})"
            )
            return jsonify(result)
        except Exception:
            logger.exception(f"channel.update: err (user_id={user_id}, ch_id={channel_id})")
            return jsonify({"error": "internal_error"}), 500

    @auth_required
    def delete(self, channel_id: int, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        try:
            result = delete_channel(db, user_id, channel_id)
            if "error" in result:
                logger.info(f"channel.delete: not_found (user_id={user_id}, ch_id={channel_id})")
                return jsonify(result), 404

            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"channel.delete: ok (user_id={user_id}, ch_id={channel_id}, dt_ms={dt:.0f})"
            )
            return jsonify(result)
        except Exception:
            logger.exception(f"channel.delete: err (user_id={user_id}, ch_id={channel_id})")
            return jsonify({"error": "internal_error"}), 500
