# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

from time import perf_counter
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from ..auth import auth_required
from ..logger import logger
from ..services.channels_service import (
    list_channels,
    create_channel,
    update_channel,
    delete_channel,
)

bp_channels = Blueprint("channels", __name__, url_prefix="/api")


@bp_channels.get("/channels")
@auth_required
def channels_list(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    try:
        items = list_channels(db, uid)
        dt = (perf_counter() - t0) * 1000
        logger.info(f"channels.list: ok (user_id={uid}, n={len(items)}, dt_ms={dt:.0f})")
        return jsonify({"items": items})
    except Exception:
        logger.exception(f"channels.list: err (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_channels.post("/channel")
@auth_required
def channel_create(db: Session):
    t0 = perf_counter()
    uid = request.user_id
    d = request.get_json(silent=True) or {}
    try:
        r = create_channel(
            db,
            uid,
            d.get("channel_id"),
            d.get("price_min"),
            d.get("price_max"),
            d.get("supply_min"),
            d.get("supply_max"),
            (d.get("title") or "").strip() or None,
        )
        if "error" in r:
            code = 409 if r["error"] == "duplicate_channel" else 400
            logger.info(
                f"channel.create: fail (user_id={uid}, err={r.get('error')}, detail={r.get('detail','')})"
            )
            return jsonify(r), code

        dt = (perf_counter() - t0) * 1000
        logger.info(
            f"channel.create: ok (user_id={uid}, channel_row_id={r['channel_id']}, dt_ms={dt:.0f})"
        )
        return jsonify(r)
    except ValueError as e:
        logger.info(f"channel.create: bad_channel_id (user_id={uid}, detail={e})")
        return jsonify({"error": "bad_channel_id", "detail": str(e)}), 400
    except Exception:
        logger.exception(f"channel.create: err (user_id={uid})")
        return jsonify({"error": "internal_error"}), 500


@bp_channels.patch("/channel/<int:ch_id>")
@auth_required
def channel_update(ch_id: int, db: Session):
    t0 = perf_counter()
    uid = request.user_id
    d = request.get_json(silent=True) or {}
    try:
        r = update_channel(db, uid, ch_id, **d)
        if "error" in r:
            logger.info(f"channel.update: not_found (user_id={uid}, ch_id={ch_id})")
            return jsonify(r), 404

        dt = (perf_counter() - t0) * 1000
        logger.info(f"channel.update: ok (user_id={uid}, ch_id={ch_id}, dt_ms={dt:.0f})")
        return jsonify(r)
    except Exception:
        logger.exception(f"channel.update: err (user_id={uid}, ch_id={ch_id})")
        return jsonify({"error": "internal_error"}), 500


@bp_channels.delete("/channel/<int:ch_id>")
@auth_required
def channel_delete(ch_id: int, db: Session):
    t0 = perf_counter()
    uid = request.user_id
    try:
        r = delete_channel(db, uid, ch_id)
        if "error" in r:
            logger.info(f"channel.delete: not_found (user_id={uid}, ch_id={ch_id})")
            return jsonify(r), 404

        dt = (perf_counter() - t0) * 1000
        logger.info(f"channel.delete: ok (user_id={uid}, ch_id={ch_id}, dt_ms={dt:.0f})")
        return jsonify(r)
    except Exception:
        logger.exception(f"channel.delete: err (user_id={uid}, ch_id={ch_id})")
        return jsonify({"error": "internal_error"}), 500
