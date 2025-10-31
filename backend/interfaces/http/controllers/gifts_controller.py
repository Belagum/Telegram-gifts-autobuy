# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import gzip
import hashlib
import json
import threading
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from queue import Queue
from typing import Any, cast

import httpx
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from sqlalchemy.orm import Session, joinedload

from backend.infrastructure.audit import AuditAction, audit_log
from backend.infrastructure.auth import auth_required, authed_request
from backend.infrastructure.db.models import Account, User, UserSettings
from backend.services.gifts_service import (
    NoAccountsError,
    gifts_event_bus,
    read_user_gifts,
    refresh_once,
    start_user_gifts,
    stop_user_gifts,
)
from backend.services.tg_clients_service import tg_call
from backend.shared.errors import (
    AccountNotFoundError,
    ApiProfileMissingError,
    BadTgsError,
    GiftNotFoundError,
    GiftUnavailableError,
    InfrastructureError,
    InsufficientBalanceError,
    InvalidAccountIdError,
    InvalidGiftIdError,
    PeerIdInvalidError,
    TargetIdInvalidError,
    TargetIdRequiredError,
)
from backend.shared.logging import logger
from backend.shared.middleware.csrf import csrf_protect
from backend.shared.utils.asyncio_utils import run_async as _run_async
from backend.shared.utils.fs import link_or_copy, save_atomic
from backend.shared.utils.http import etag_for_path

_FILE_LOCKS: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)


def _cache_base_dir() -> Path:
    base = current_app.config.get("GIFTS_CACHE_DIR")
    return Path(base) if base else Path(current_app.instance_path) / "gifts_cache"


def _shard_dir(key: str) -> Path:
    shard = hashlib.sha1(key.encode("utf-8")).hexdigest()[:2]
    return _cache_base_dir() / shard


def _cached_path_for(key: str) -> Path:
    return _shard_dir(key) / f"{key}.tgs"


def _find_cached_tgs(key: str) -> Path | None:
    path = _cached_path_for(key)
    return path if path.exists() and path.stat().st_size > 0 else None


async def _botapi_download(file_id: str, token: str) -> bytes:
    if not token:
        raise RuntimeError("no_bot_token")
    api = f"https://api.telegram.org/bot{token}"
    base = f"https://api.telegram.org/file/bot{token}"
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.get(f"{api}/getFile", params={"file_id": file_id})
        response.raise_for_status()
        payload = response.json()
        if not (payload.get("ok") and payload.get("result") and payload["result"].get("file_path")):
            raise RuntimeError("getFile error")
        file_path = payload["result"]["file_path"]
        response2 = await http.get(f"{base}/{file_path}", follow_redirects=True)
        response2.raise_for_status()
        return response2.content


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _send_lottie_json_from_tgs(path: Path) -> Response | tuple[Response, int]:
    etag = etag_for_path(path)
    if_none_match = (request.headers.get("If-None-Match") or "").strip()
    if if_none_match == etag:
        response = Response(status=304)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["ETag"] = etag
        return response
    raw = path.read_bytes()
    try:
        data = gzip.decompress(raw)
    except Exception as exc:
        raise BadTgsError() from exc
    response = Response(data, mimetype="application/json")
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["ETag"] = etag
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _promote_cached(src_key: str, dst_key: str) -> Path | None:
    if src_key == dst_key:
        return _find_cached_tgs(dst_key)
    dst_lock = _FILE_LOCKS[dst_key]
    with dst_lock:
        dst = _find_cached_tgs(dst_key)
        if dst:
            return dst
        src = _find_cached_tgs(src_key)
        if not src:
            return None
        dst_path = _cached_path_for(dst_key)
        try:
            link_or_copy(src, dst_path)
        except Exception:
            logger.exception("promote cache failed")
            return None
        return dst_path


def _parse_iso_to_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


def _convert_gift_ids_to_strings(gifts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for gift in gifts:
        gift_copy = gift.copy()
        if "id" in gift_copy and isinstance(gift_copy["id"], int):
            gift_copy["id"] = str(gift_copy["id"])
        result.append(gift_copy)
    return result


class GiftsController:
    def as_blueprint(self) -> Blueprint:
        bp = Blueprint("gifts", __name__, url_prefix="/api")
        bp.add_url_rule("/gifts", view_func=self.list_gifts, methods=["GET"], endpoint="gifts_list")
        bp.add_url_rule(
            "/gifts/refresh",
            view_func=self.refresh_gifts,
            methods=["POST"],
            endpoint="gifts_refresh",
        )
        bp.add_url_rule(
            "/gifts/<string:gift_id>/buy",
            view_func=self.buy_gift,
            methods=["POST"],
            endpoint="gifts_buy",
        )
        bp.add_url_rule(
            "/gifts/sticker.lottie",
            view_func=self.sticker_lottie,
            methods=["GET"],
            endpoint="gifts_sticker_lottie",
        )
        bp.add_url_rule(
            "/gifts/settings",
            view_func=self.settings_get,
            methods=["GET"],
            endpoint="gifts_settings",
        )
        bp.add_url_rule(
            "/gifts/settings",
            view_func=self.settings_set,
            methods=["POST"],
            endpoint="gifts_settings_set",
        )
        bp.add_url_rule(
            "/gifts/stream",
            view_func=self.stream,
            methods=["GET"],
            endpoint="gifts_stream",
        )
        return bp

    @auth_required
    def list_gifts(self, _db: Session):
        items = read_user_gifts(authed_request().user_id)
        return jsonify({"items": _convert_gift_ids_to_strings(items)})

    @auth_required
    @csrf_protect
    def refresh_gifts(self, _db: Session) -> Response | tuple[Response, int]:
        want_stream = request.args.get("stream") == "1" or "application/x-ndjson" in (
            request.headers.get("Accept") or ""
        )
        if not want_stream:
            try:
                user_id = authed_request().user_id
                items = refresh_once(user_id)
                
                audit_log(
                    AuditAction.GIFTS_REFRESH,
                    user_id=user_id,
                    ip_address=request.remote_addr,
                    details={"items_count": len(items)},
                    success=True,
                )
                
                return jsonify({"items": _convert_gift_ids_to_strings(items)})
            except NoAccountsError:
                return jsonify({"error": "no_accounts"}), 409

        def gen() -> Iterator[bytes]:
            def line(obj: dict[str, Any]) -> bytes:
                text: str = json.dumps(obj, ensure_ascii=False)
                return (text + "\n").encode("utf-8")

            yield line({"stage": "start"})
            try:
                items = refresh_once(authed_request().user_id)
                items = _convert_gift_ids_to_strings(items)
                yield line({"stage": "fetched", "count": len(items)})
                yield line({"stage": "done", "items": items})
            except NoAccountsError:
                yield line({"stage": "error", "error": "no_accounts"})
            except Exception:
                logger.exception("gifts_refresh stream failed")
                yield line({"stage": "error", "error": "internal"})

        wrapped = cast(Callable[[], Iterator[bytes]], stream_with_context(gen))
        response = Response(wrapped(), mimetype="application/x-ndjson")
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @auth_required
    @csrf_protect
    def buy_gift(self, gift_id: str, db: Session) -> Response | tuple[Response, int]:
        payload = request.get_json(silent=True) or {}
        account_raw = payload.get("account_id")
        target_raw = payload.get("target_id")

        try:
            gift_id_int = int(gift_id)
        except (TypeError, ValueError) as exc:
            raise InvalidGiftIdError(gift_id) from exc

        account_id = _parse_int(account_raw)
        if account_id is None or account_id <= 0:
            raise InvalidAccountIdError()

        target_text = str(target_raw or "").strip()
        if not target_text:
            raise TargetIdRequiredError()
        target_id = _parse_int(target_text)
        if target_id is None:
            raise TargetIdInvalidError()

        user_id = authed_request().user_id

        account = (
            db.query(Account)
            .options(joinedload(Account.api_profile))
            .filter(Account.user_id == user_id, Account.id == account_id)
            .first()
        )
        if not account:
            raise AccountNotFoundError(account_id)
        if not account.api_profile:
            raise ApiProfileMissingError()

        items = read_user_gifts(user_id)
        gift = next(
            (
                row
                for row in items
                if isinstance(row.get("id"), int) and int(row.get("id", 0)) == gift_id_int
            ),
            None,
        )
        if not gift:
            raise GiftNotFoundError(gift_id_int)

        limited = bool(gift.get("is_limited"))
        available_amount = _parse_int(gift.get("available_amount"))
        if limited and (available_amount is None or available_amount <= 0):
            raise GiftUnavailableError()

        locks = gift.get("locks") if isinstance(gift.get("locks"), dict) else {}
        lock_value = None
        if isinstance(locks, dict):
            lock_value = locks.get(str(account_id)) or locks.get(account_id)
        lock_until = _parse_iso_to_utc(lock_value if isinstance(lock_value, str) else None)
        now_utc = datetime.now(UTC)
        if lock_until and lock_until > now_utc:
            remaining_seconds = int((lock_until - now_utc).total_seconds())
            payload = {
                "error": "gift_locked",
                "context": {
                    "account_id": account_id,
                    "locked_until": lock_until.isoformat().replace("+00:00", "Z"),
                    "remaining_seconds": max(remaining_seconds, 0),
                },
            }
            return jsonify(payload), 409

        if bool(gift.get("require_premium")) and not bool(getattr(account, "is_premium", False)):
            return jsonify({"error": "requires_premium"}), 409

        async def _send_once() -> None:
            async def _call(client):
                return await client.send_gift(chat_id=int(target_id), gift_id=gift_id_int)

            await tg_call(
                account.session_path,
                account.api_profile.api_id,
                account.api_profile.api_hash,
                _call,
                min_interval=0.7,
            )

        try:
            _run_async(_send_once())
        except Exception as exc:  # pragma: no cover - network issues
            logger.exception(
                f"gifts.buy failed user_id={user_id} gift_id={gift_id} account_id={account_id} "
                f"target_id={target_id}"
            )
            
            audit_log(
                AuditAction.GIFT_SEND_FAILED,
                user_id=user_id,
                ip_address=request.remote_addr,
                details={
                    "gift_id": gift_id,
                    "account_id": account_id,
                    "target_id": target_id,
                    "error": str(exc),
                },
                success=False,
            )
            
            message = (str(exc) or "").upper()
            if "BALANCE_TOO_LOW" in message:
                try:
                    async def _get_balance(client):
                        return await client.get_stars_balance()
                    
                    balance = int(
                        _run_async(
                            tg_call(
                                account.session_path,
                                account.api_profile.api_id,
                                account.api_profile.api_hash,
                                _get_balance,
                                min_interval=0.5,
                            )
                        )
                    )
                except Exception:
                    balance = 0
                price = _parse_int(gift.get("price")) or 0
                raise InsufficientBalanceError(balance, price) from None
            if (
                "PEER_ID_INVALID" in message
                or "PEER ID INVALID" in message
                or "USER_ID_INVALID" in message
                or "CHAT_ID_INVALID" in message
            ):
                raise PeerIdInvalidError() from None
            raise InfrastructureError(code="gift_send_failed") from exc

        logger.info(
            f"gifts.buy success user_id={user_id} gift_id={gift_id} account_id={account_id} "
            f"target_id={target_id}"
        )
        
        audit_log(
            AuditAction.GIFT_SENT,
            user_id=user_id,
            ip_address=request.remote_addr,
            details={
                "gift_id": gift_id,
                "account_id": account_id,
                "target_id": target_id,
                "price": gift.get("price"),
            },
            success=True,
        )

        return jsonify(
            {
                "ok": True,
                "result": "gift_sent",
                "context": {
                    "gift_id": gift_id,
                    "account_id": account_id,
                    "target_id": target_id,
                },
            }
        )

    @auth_required
    def sticker_lottie(self, db: Session):
        file_id = (request.args.get("file_id") or "").strip()
        uniq = (request.args.get("uniq") or "").strip()
        if not file_id and not uniq:
            return jsonify({"error": "file_id_or_uniq_required"}), 400
        cache_key = uniq or file_id
        path = _find_cached_tgs(cache_key)
        if not path and uniq and file_id:
            path = _promote_cached(file_id, uniq)
        if not path and file_id:
            lock = _FILE_LOCKS[cache_key]
            with lock:
                path = _find_cached_tgs(cache_key)
                if not path:
                    settings = db.get(UserSettings, authed_request().user_id)
                    token = (getattr(settings, "bot_token", "") or "").strip()
                    if not token:
                        return jsonify({"error": "no_bot_token"}), 409
                    try:
                        data = _run_async(_botapi_download(file_id, token))
                        if not (len(data) >= 2 and data[:2] == b"\x1f\x8b"):
                            return jsonify({"error": "bad_tgs"}), 415
                        target = _cached_path_for(cache_key)
                        save_atomic(target, data)
                        path = target
                    except Exception:
                        logger.exception("bot download failed")
                        return jsonify({"error": "download_failed"}), 502
        if not path:
            return jsonify({"error": "download_failed"}), 502
        return _send_lottie_json_from_tgs(path)

    @auth_required
    def settings_get(self, db: Session) -> Response | tuple[Response, int]:
        user = db.get(User, authed_request().user_id)
        if not user:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"auto_refresh": bool(getattr(user, "gifts_autorefresh", False))})

    @auth_required
    @csrf_protect
    def settings_set(self, db: Session) -> Response | tuple[Response, int]:
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get("auto_refresh"))
        user_id = authed_request().user_id
        user = db.get(User, user_id)
        if not user:
            return jsonify({"error": "not_found"}), 404
        user.gifts_autorefresh = enabled
        db.commit()
        
        action = AuditAction.GIFTS_AUTO_REFRESH_ENABLED if enabled else AuditAction.GIFTS_AUTO_REFRESH_DISABLED
        audit_log(
            action,
            user_id=user_id,
            ip_address=request.remote_addr,
            details={"auto_refresh": enabled},
            success=True,
        )
        
        if enabled:
            start_user_gifts(user_id)
        else:
            stop_user_gifts(user_id)
        return jsonify({"ok": True, "auto_refresh": enabled})

    @auth_required
    def stream(self, _db: Session):
        user_id = authed_request().user_id

        def sse(event: str, data: dict[str, Any]) -> bytes:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()

        queue: Queue = gifts_event_bus.subscribe(user_id)

        @stream_with_context
        def gen() -> Iterator[bytes]:
            try:
                snapshot = read_user_gifts(user_id)
                snapshot = _convert_gift_ids_to_strings(snapshot)
                yield sse("gifts", {"items": snapshot, "count": len(snapshot)})
                last_ping = time.monotonic()
                while True:
                    try:
                        event = queue.get(timeout=10.0)
                        if event and event.get("items") is not None:
                            event_copy = event.copy()
                            event_copy["items"] = _convert_gift_ids_to_strings(event["items"])
                            yield sse("gifts", event_copy)
                    except Exception:
                        pass
                    if time.monotonic() - last_ping > 25:
                        yield b": ping\n\n"
                        last_ping = time.monotonic()
            finally:
                gifts_event_bus.unsubscribe(user_id, queue)

        stream_fn = cast(Callable[[], Iterator[bytes]], gen)
        return Response(
            stream_fn(),
            headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
