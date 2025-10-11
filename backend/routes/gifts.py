# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

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

from ..auth import auth_required, authed_request
from ..logger import logger
from ..models import Account, User, UserSettings
from ..services.gifts_service import (
    NoAccountsError,
    gifts_event_bus,
    read_user_gifts,
    refresh_once,
    start_user_gifts,
    stop_user_gifts,
)
from ..services.tg_clients_service import get_stars_balance, tg_call
from ..utils.asyncio_utils import run_async as _run_async
from ..utils.fs import link_or_copy, save_atomic
from ..utils.http import etag_for_path

bp_gifts = Blueprint("gifts", __name__, url_prefix="/api")

_FILE_LOCKS: dict[str, threading.Lock] = defaultdict(threading.Lock)


def _cache_base_dir() -> Path:
    base = current_app.config.get("GIFTS_CACHE_DIR")
    return Path(base) if base else Path(current_app.instance_path) / "gifts_cache"


def _shard_dir(key: str) -> Path:
    shard = hashlib.sha1(key.encode("utf-8")).hexdigest()[:2]
    return _cache_base_dir() / shard


def _cached_path_for(key: str) -> Path:
    return _shard_dir(key) / f"{key}.tgs"


def _find_cached_tgs(key: str) -> Path | None:
    p = _cached_path_for(key)
    return p if p.exists() and p.stat().st_size > 0 else None


async def _botapi_download(file_id: str, token: str) -> bytes:
    if not token:
        raise RuntimeError("no_bot_token")
    api = f"https://api.telegram.org/bot{token}"
    base = f"https://api.telegram.org/file/bot{token}"
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(f"{api}/getFile", params={"file_id": file_id})
        r.raise_for_status()
        p = r.json()
        if not (p.get("ok") and p.get("result") and p["result"].get("file_path")):
            raise RuntimeError("getFile error")
        fp = p["result"]["file_path"]
        r2 = await http.get(f"{base}/{fp}", follow_redirects=True)
        r2.raise_for_status()
        return cast(bytes, r2.content)


def _send_lottie_json_from_tgs(path: Path) -> Response | tuple[Response, int]:
    etag = etag_for_path(path)
    inm = (request.headers.get("If-None-Match") or "").strip()
    if inm == etag:
        resp = Response(status=304)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        resp.headers["ETag"] = etag
        return resp
    raw = path.read_bytes()
    try:
        data = gzip.decompress(raw)
    except Exception:
        return jsonify({"error": "bad_tgs"}), 415
    resp = Response(data, mimetype="application/json")
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    resp.headers["ETag"] = etag
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


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
    result = []
    for gift in gifts:
        gift_copy = gift.copy()
        if "id" in gift_copy and isinstance(gift_copy["id"], int):
            gift_copy["id"] = str(gift_copy["id"])
        result.append(gift_copy)
    return result


@bp_gifts.get("/gifts", endpoint="gifts_list")
@auth_required
def gifts_list(db: Session):
    items = read_user_gifts(authed_request().user_id)
    return jsonify({"items": _convert_gift_ids_to_strings(items)})


@bp_gifts.post("/gifts/refresh", endpoint="gifts_refresh")
@auth_required
def gifts_refresh(db: Session) -> Response | tuple[Response, int]:
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
        def line(o: dict[str, Any]) -> bytes:
            text: str = json.dumps(o, ensure_ascii=False)
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
    resp = Response(wrapped(), mimetype="application/x-ndjson")
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@bp_gifts.post("/gifts/<string:gift_id>/buy", endpoint="gifts_buy")
@auth_required
def gifts_buy(gift_id: str, db: Session) -> Response | tuple[Response, int]:
    payload = request.get_json(silent=True) or {}
    account_raw = payload.get("account_id")
    target_raw = (payload.get("target_id") or "").strip()

    try:
        gift_id_int = int(gift_id)
    except (TypeError, ValueError):
        return jsonify({"error": "gift_id_invalid"}), 400

    try:
        account_id = int(account_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "account_id_invalid"}), 400
    if account_id <= 0:
        return jsonify({"error": "account_id_invalid"}), 400

    if not target_raw:
        return jsonify({"error": "target_id_required"}), 400
    try:
        target_id = int(target_raw)
    except ValueError:
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
    available_raw = gift.get("available_amount")
    try:
        available_amount = int(available_raw)
    except (TypeError, ValueError):
        available_amount = None
    if limited and (available_amount is None or available_amount <= 0):
        return jsonify({"error": "gift_unavailable", "detail": "Подарок недоступен"}), 409

    locks = gift.get("locks") if isinstance(gift.get("locks"), dict) else {}
    lock_value = None
    if isinstance(locks, dict):
        lock_value = locks.get(str(account_id)) or locks.get(account_id)
    lock_until = _parse_iso_to_utc(lock_value if isinstance(lock_value, str) else None)
    if lock_until and lock_until > datetime.now(UTC):
        remaining = _format_remaining(lock_until - datetime.now(UTC))
        detail = (
            f"Аккаунт {account_id} заблокирован до {lock_until.isoformat().replace('+00:00', 'Z')}"
        )
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
            try:
                price = int(gift.get("price", 0) or 0)
            except Exception:
                price = 0
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
        # Telegram: peer id is invalid or unknown for this account
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
        msg = str(exc)
        return jsonify({"error": "send_failed", "detail": (msg or "")[:200]}), 502

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


@bp_gifts.get("/gifts/sticker.lottie", endpoint="gifts_sticker_lottie")
@auth_required
def gifts_sticker_lottie(db: Session):
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
                s = db.get(UserSettings, authed_request().user_id)
                token = (getattr(s, "bot_token", "") or "").strip()
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


@bp_gifts.get("/gifts/settings", endpoint="gifts_settings")
@auth_required
def gifts_settings(db: Session) -> Response | tuple[Response, int]:
    u = db.get(User, authed_request().user_id)
    if not u:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"auto_refresh": bool(getattr(u, "gifts_autorefresh", False))})


@bp_gifts.post("/gifts/settings", endpoint="gifts_settings_set")
@auth_required
def gifts_settings_set(db: Session) -> Response | tuple[Response, int]:
    d = request.get_json(silent=True) or {}
    en = bool(d.get("auto_refresh"))
    uid = authed_request().user_id
    u = db.get(User, uid)
    if not u:
        return jsonify({"error": "not_found"}), 404
    u.gifts_autorefresh = en
    db.commit()
    if en:
        start_user_gifts(uid)
    else:
        stop_user_gifts(uid)
    return jsonify({"ok": True, "auto_refresh": en})


@bp_gifts.get("/gifts/stream", endpoint="gifts_stream")
@auth_required
def gifts_stream(db: Session):
    user_id = authed_request().user_id

    def sse(event: str, data: dict[str, Any]) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()

    q: Queue = gifts_event_bus.subscribe(user_id)

    @stream_with_context
    def gen() -> Iterator[bytes]:
        try:
            snap = read_user_gifts(user_id)
            snap = _convert_gift_ids_to_strings(snap)
            yield sse("gifts", {"items": snap, "count": len(snap)})
            last_ping = time.monotonic()
            while True:
                try:
                    evt = q.get(timeout=10.0)
                    if evt and evt.get("items") is not None:
                        evt_copy = evt.copy()
                        evt_copy["items"] = _convert_gift_ids_to_strings(evt["items"])
                        yield sse("gifts", evt_copy)
                except Exception:
                    pass
                if time.monotonic() - last_ping > 25:
                    yield b": ping\n\n"
                    last_ping = time.monotonic()
        finally:
            gifts_event_bus.unsubscribe(user_id, q)

    stream_fn = cast(Callable[[], Iterator[bytes]], gen)
    return Response(
        stream_fn(),
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
