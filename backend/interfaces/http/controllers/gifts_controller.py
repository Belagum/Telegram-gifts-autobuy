# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""HTTP controller for gifts-related endpoints."""

from __future__ import annotations

import gzip
import hashlib
import json
import threading
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from queue import Queue
from typing import Any, cast

import httpx
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from sqlalchemy.orm import Session, joinedload

from backend.auth import auth_required, authed_request
from backend.infrastructure.db.models import Account, User, UserSettings
from backend.services.gifts_service import (
    NoAccountsError,
    gifts_event_bus,
    read_user_gifts,
    refresh_once,
    start_user_gifts,
    stop_user_gifts,
)
from backend.services.tg_clients_service import get_stars_balance, tg_call
from backend.shared.logging import logger
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
    except Exception:
        return jsonify({"error": "bad_tgs"}), 415
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


def _format_remaining(delta: timedelta) -> str:
    seconds = int(max(delta.total_seconds(), 0))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")
    if not parts:
        parts.append(f"{seconds}с")
    return " ".join(parts)


def _convert_gift_ids_to_strings(gifts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for gift in gifts:
        gift_copy = gift.copy()
        if "id" in gift_copy and isinstance(gift_copy["id"], int):
            gift_copy["id"] = str(gift_copy["id"])
        result.append(gift_copy)
    return result


class GiftsController:
    """Controller exposing gifts endpoints."""

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
    def refresh_gifts(self, _db: Session) -> Response | tuple[Response, int]:
        want_stream = request.args.get("stream") == "1" or "application/x-ndjson" in (
            request.headers.get("Accept") or ""
        )
        if not want_stream:
            try:
                items = refresh_once(authed_request().user_id)
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
    def buy_gift(self, gift_id: str, db: Session) -> Response | tuple[Response, int]:
        payload = request.get_json(silent=True) or {}
        account_raw = payload.get("account_id")
        target_raw = payload.get("target_id")

        try:
            gift_id_int = int(gift_id)
        except (TypeError, ValueError):
            return jsonify({"error": "gift_id_invalid"}), 400

        account_id = _parse_int(account_raw)
        if account_id is None or account_id <= 0:
            return jsonify({"error": "account_id_invalid"}), 400

        target_text = str(target_raw or "").strip()
        if not target_text:
            return jsonify({"error": "target_id_required"}), 400
        target_id = _parse_int(target_text)
        if target_id is None:
            return jsonify({"error": "target_id_invalid"}), 400

        user_id = authed_request().user_id

        account = (
            db.query(Account)
            .options(joinedload(Account.api_profile))
            .filter(Account.user_id == user_id, Account.id == account_id)
            .first()
        )
        if not account:
            return jsonify({"error": "account_not_found"}), 404
        if not account.api_profile:
            return jsonify({"error": "api_profile_missing"}), 409

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
            return jsonify({"error": "gift_not_found"}), 404

        limited = bool(gift.get("is_limited"))
        available_amount = _parse_int(gift.get("available_amount"))
        if limited and (available_amount is None or available_amount <= 0):
            return jsonify({"error": "gift_unavailable", "detail": "Подарок недоступен"}), 409

        locks = gift.get("locks") if isinstance(gift.get("locks"), dict) else {}
        lock_value = None
        if isinstance(locks, dict):
            lock_value = locks.get(str(account_id)) or locks.get(account_id)
        lock_until = _parse_iso_to_utc(lock_value if isinstance(lock_value, str) else None)
        if lock_until and lock_until > datetime.now(UTC):
            remaining = _format_remaining(lock_until - datetime.now(UTC))
            lock_text = lock_until.isoformat().replace("+00:00", "Z")
            detail = f"Аккаунт {account_id} заблокирован до {lock_text}"
            if remaining:
                detail = f"{detail} (ещё {remaining})"
            return jsonify({"error": "gift_locked", "detail": detail}), 409

        if bool(gift.get("require_premium")) and not bool(getattr(account, "is_premium", False)):
            return jsonify({"error": "requires_premium", "detail": "Аккаунт без Premium"}), 409

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
                "gifts.buy failed user_id={} gift_id={} account_id={} target_id={}",
                user_id,
                gift_id,
                account_id,
                target_id,
            )
            message = (str(exc) or "").upper()
            if "BALANCE_TOO_LOW" in message:
                try:
                    balance = int(
                        _run_async(
                            get_stars_balance(
                                account.session_path,
                                account.api_profile.api_id,
                                account.api_profile.api_hash,
                                min_interval=0.5,
                            )
                        )
                    )
                except Exception:
                    balance = 0
                price = _parse_int(gift.get("price")) or 0
                detail = f"Недостаточно Stars: баланс {balance}⭐, нужно {price}⭐"
                return (
                    jsonify(
                        {
                            "error": "insufficient_balance",
                            "detail": detail,
                            "balance": balance,
                            "price": price,
                            "gift_id": gift_id,
                            "account_id": account_id,
                            "target_id": target_id,
                        }
                    ),
                    409,
                )
            if "PEER_ID_INVALID" in message or "PEER ID INVALID" in message:
                return (
                    jsonify(
                        {
                            "error": "peer_id_invalid",
                            "detail": (
                                "Некорректный или неизвестный получатель. "
                                "Убедитесь, что указали правильный ID и что выбранный аккаунт "
                                "уже встречал этот чат/канал (начните диалог или вступите в канал)."
                            ),
                            "account_id": account_id,
                            "target_id": target_id,
                            "gift_id": gift_id,
                        }
                    ),
                    409,
                )
            message_text = str(exc)
            return jsonify({"error": "send_failed", "detail": (message_text or "")[:200]}), 502

        logger.info(
            "gifts.buy success user_id={} gift_id={} account_id={} target_id={}",
            user_id,
            gift_id,
            account_id,
            target_id,
        )

        return jsonify(
            {
                "ok": True,
                "message": f"Подарок {gift_id} отправлен с аккаунта {account_id}",
                "gift_id": gift_id,
                "account_id": account_id,
                "target_id": target_id,
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
                    _shard_dir(cache_key).mkdir(parents=True, exist_ok=True)
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
    def settings_set(self, db: Session) -> Response | tuple[Response, int]:
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get("auto_refresh"))
        user_id = authed_request().user_id
        user = db.get(User, user_id)
        if not user:
            return jsonify({"error": "not_found"}), 404
        user.gifts_autorefresh = enabled
        db.commit()
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
