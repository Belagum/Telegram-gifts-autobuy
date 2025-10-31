# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig


from __future__ import annotations

from time import perf_counter

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session

from backend.infrastructure.audit import AuditAction, audit_log
from backend.infrastructure.auth import auth_required, authed_request
from backend.services.channels_service import (
    create_channel,
    delete_channel,
    list_channels,
    update_channel,
)
from backend.shared.errors import (
    BadChannelIdError,
    ChannelNotFoundError,
    DuplicateChannelError,
    InfrastructureError,
)
from backend.shared.logging import logger
from backend.shared.middleware.csrf import csrf_protect


class ChannelsController:
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
        except Exception as exc:
            logger.exception(f"channels.list: err (user_id={user_id})")
            raise InfrastructureError(code="channels_list_failed") from exc

    @auth_required
    @csrf_protect
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
                error_code = result["error"]
                if error_code == "duplicate_channel":
                    channel_id = payload.get("channel_id")
                    raise DuplicateChannelError(channel_id)
                else:
                    raise BadChannelIdError(str(payload.get("channel_id", "")))

            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"channel.create: ok (user_id={user_id}, channel_row_id={result['channel_id']}, "
                f"dt_ms={dt:.0f})"
            )
            
            audit_log(
                AuditAction.CHANNEL_ADDED,
                user_id=user_id,
                ip_address=request.remote_addr,
                details={
                    "channel_id": payload.get("channel_id"),
                    "title": payload.get("title"),
                    "price_min": payload.get("price_min"),
                    "price_max": payload.get("price_max"),
                },
                success=True,
            )
            
            return jsonify(result)
        except (DuplicateChannelError, BadChannelIdError):
            raise
        except ValueError as exc:
            logger.info(f"channel.create: bad_channel_id (user_id={user_id}, detail={exc})")
            raise BadChannelIdError(str(payload.get("channel_id", ""))) from exc
        except Exception as exc:
            logger.exception(f"channel.create: err (user_id={user_id})")
            raise InfrastructureError(code="channel_create_failed") from exc

    @auth_required
    @csrf_protect
    def update(self, channel_id: int, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        payload = request.get_json(silent=True) or {}
        try:
            result = update_channel(db, user_id, channel_id, **payload)
            if "error" in result:
                logger.info(f"channel.update: not_found (user_id={user_id}, ch_id={channel_id})")
                raise ChannelNotFoundError(channel_id)

            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"channel.update: ok (user_id={user_id}, ch_id={channel_id}, dt_ms={dt:.0f})"
            )
            
            audit_log(
                AuditAction.CHANNEL_UPDATED,
                user_id=user_id,
                ip_address=request.remote_addr,
                details={
                    "channel_id": channel_id,
                    "updated_fields": payload,
                },
                success=True,
            )
            
            return jsonify(result)
        except ChannelNotFoundError:
            raise
        except Exception as exc:
            logger.exception(f"channel.update: err (user_id={user_id}, ch_id={channel_id})")
            raise InfrastructureError(code="channel_update_failed") from exc

    @auth_required
    @csrf_protect
    def delete(self, channel_id: int, db: Session):
        t0 = perf_counter()
        user_id = authed_request().user_id
        try:
            result = delete_channel(db, user_id, channel_id)
            if "error" in result:
                logger.info(f"channel.delete: not_found (user_id={user_id}, ch_id={channel_id})")
                raise ChannelNotFoundError(channel_id)

            dt = (perf_counter() - t0) * 1000
            logger.info(
                f"channel.delete: ok (user_id={user_id}, ch_id={channel_id}, dt_ms={dt:.0f})"
            )
            
            audit_log(
                AuditAction.CHANNEL_REMOVED,
                user_id=user_id,
                ip_address=request.remote_addr,
                details={"channel_id": channel_id},
                success=True,
            )
            
            return jsonify(result)
        except ChannelNotFoundError:
            raise
        except Exception as exc:
            logger.exception(f"channel.delete: err (user_id={user_id}, ch_id={channel_id})")
            raise InfrastructureError(code="channel_delete_failed") from exc
