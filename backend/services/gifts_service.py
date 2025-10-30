# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import asyncio
import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from queue import Queue
from typing import Any, cast

from sqlalchemy.orm import Session, joinedload

from backend.application.use_cases.autobuy import AutobuyOutput
from backend.infrastructure.container import container

from ..infrastructure.db import SessionLocal
from ..infrastructure.db.models import Account
from ..shared.logging import logger
from ..shared.utils.gifts_utils import hash_items, merge_new
from ..shared.utils.jsonio import read_json_list_of_dicts, write_json_list
from .notify_gifts_service import broadcast_new_gifts
from .tg_clients_service import tg_call, tg_shutdown
from backend.shared.config import load_config

@dataclass
class _WorkerState:
    stop: threading.Event
    thread: threading.Thread | None = None


_config = load_config()

GIFTS_THREADS: dict[int, _WorkerState] = {}
_GIFTS_DIR = str(_config.gifts_dir)
ACC_TTL = float(_config.gifts_accs_ttl)


class NoAccountsError(Exception):
    pass


def _gifts_path(uid: int) -> str:
    return os.path.join(_GIFTS_DIR, f"user_{uid}.json")


def _ensure_dir() -> None:
    try:
        os.makedirs(_GIFTS_DIR, exist_ok=True)
    except Exception:
        pass


class _GiftsEventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subs: dict[int, list[Queue]] = {}

    def subscribe(self, user_id: int) -> Queue:
        q: Queue = Queue()
        with self._lock:
            self._subs.setdefault(user_id, []).append(q)
        return q

    def unsubscribe(self, user_id: int, q: Queue) -> None:
        with self._lock:
            arr = self._subs.get(user_id, [])
            if q in arr:
                arr.remove(q)
            if not arr and user_id in self._subs:
                self._subs.pop(user_id, None)

    def publish(self, user_id: int, payload: dict[str, Any]) -> None:
        with self._lock:
            arr = list(self._subs.get(user_id, []))
        for q in arr:
            try:
                q.put_nowait(payload)
            except Exception:
                pass


gifts_event_bus = _GiftsEventBus()


async def _list_gifts_for_account_persist(
    session_path: str, api_id: int, api_hash: str
) -> list[dict[str, Any]]:
    gifts = cast(
        list[Any],
        await tg_call(
            session_path, api_id, api_hash, lambda c: c.get_available_gifts(), min_interval=0.8
        ),
    )
    out: list[dict[str, Any]] = []
    append = out.append
    for g in gifts or []:
        append(_normalize_gift(g))
    return out


def _normalize_gift(gift: Any) -> dict[str, Any]:
    raw = getattr(gift, "raw", None)
    sticker = getattr(gift, "sticker", None)

    is_limited = bool(getattr(gift, "is_limited", False))
    available_amount = _safe_int(getattr(gift, "available_amount", None)) if is_limited else None

    limited_per_user = bool(getattr(raw, "limited_per_user", False))
    per_user_remains = (
        _safe_int(getattr(raw, "per_user_remains", None)) if limited_per_user else None
    )
    per_user_available: int | None
    if limited_per_user:
        if available_amount is not None and per_user_remains is not None:
            per_user_available = min(available_amount, per_user_remains)
        else:
            per_user_available = per_user_remains
    else:
        per_user_available = available_amount

    locked_raw = (
        getattr(gift, "locked_until_date", None)
        or getattr(raw, "locked_until_date", None)
        or getattr(gift, "locked_until", None)
        or getattr(raw, "locked_until", None)
    )

    return {
        "id": _safe_int(getattr(gift, "id", None), default=0) or 0,
        "price": _safe_int(getattr(gift, "price", None), default=0) or 0,
        "is_limited": is_limited,
        "available_amount": available_amount,
        "total_amount": _coalesce(
            getattr(gift, "total_amount", None), getattr(raw, "total_amount", None)
        ),
        "require_premium": bool(getattr(raw, "require_premium", False)),
        "limited_per_user": limited_per_user,
        "per_user_remains": per_user_remains,
        "per_user_available": per_user_available,
        "locked_until_date": _to_iso_utc(locked_raw),
        "sticker_file_id": getattr(sticker, "file_id", None),
        "sticker_unique_id": getattr(sticker, "file_unique_id", None),
        "sticker_mime": getattr(sticker, "mime_type", None),
    }


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _safe_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_iso_utc(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    timestamp = getattr(value, "timestamp", None)
    if callable(timestamp):
        try:
            return _to_iso_utc(timestamp())
        except Exception:
            return None
    return None


def _notify_run_blocking(items: list[dict[str, Any]]) -> int | Exception:
    try:
        return asyncio.run(broadcast_new_gifts(items))
    except Exception as e:
        try:
            logger.exception("gifts.notify failed in thread")
        except Exception:
            pass
        return e


async def _worker_async(uid: int) -> None:
    logger.info(f"gifts.worker: start (user_id={uid})")
    _ensure_dir()
    stop_evt = GIFTS_THREADS[uid].stop
    known_paths: set[str] = set()
    accs: list[Account] = []
    accs_loaded_at = 0.0
    i = 0
    merged_all = read_json_list_of_dicts(_gifts_path(uid))
    last_hash = hash_items(merged_all)
    try:
        while not stop_evt.is_set():
            now = time.perf_counter()
            if not accs or (now - accs_loaded_at) >= ACC_TTL:
                db: Session = SessionLocal()
                try:
                    accs = (
                        db.query(Account)
                        .options(joinedload(Account.api_profile))
                        .filter(Account.user_id == uid)
                        .order_by(Account.id.asc())
                        .all()
                    )
                    known_paths = {a.session_path for a in accs}
                    accs_loaded_at = now
                    if i >= len(accs):
                        i = 0
                finally:
                    db.close()
            n = len(accs)
            if n == 0:
                await asyncio.sleep(1.0)
                continue
            step = max(3.0 / float(n), 0.2)
            a = accs[i]
            try:
                disk_items = read_json_list_of_dicts(_gifts_path(uid))
                prev_ids = {int(x.get("id", 0)) for x in disk_items if isinstance(x.get("id"), int)}
                gifts = await _list_gifts_for_account_persist(
                    a.session_path, a.api_profile.api_id, a.api_profile.api_hash
                )
                merged_all = merge_new(disk_items or [], gifts)
                added = [
                    g
                    for g in merged_all
                    if isinstance(g.get("id"), int) and g["id"] not in prev_ids
                ]
            except Exception:
                logger.exception(f"gifts.worker: fetch failed (acc_id={a.id})")
                gifts = []
                added = []
            try:
                logger.info(
                    f"gifts.worker: iter user_id={uid} acc_id={a.id} "
                    f"gifts_now={len(gifts)} total_cached={len(merged_all)} new={len(added)}"
                )
            except Exception:
                pass
            new_hash = hash_items(merged_all)
            if new_hash != last_hash:
                last_hash = new_hash
                write_json_list(_gifts_path(uid), merged_all)
                gifts_event_bus.publish(
                    uid, {"items": merged_all, "count": len(merged_all), "hash": new_hash}
                )

                if added:
                    logger.info(f"gifts.worker: parallel start buy&notify items={len(added)}")

                    buy_task = asyncio.create_task(
                        container.autobuy_use_case.execute_with_user_check(uid, added)
                    )
                    notify_future = asyncio.to_thread(_notify_run_blocking, added)

                    res: dict[str, Any] = {
                        "purchased": [],
                        "skipped": len(added),
                        "stats": {},
                        "deferred": [],
                    }
                    stats: dict[str, Any] = {}
                    sent = 0

                    buy_res, notify_res = await asyncio.gather(
                        buy_task, notify_future, return_exceptions=True
                    )

                    if isinstance(buy_res, AutobuyOutput):
                        res = {
                            "purchased": buy_res.purchased,
                            "skipped": buy_res.skipped,
                            "stats": buy_res.stats,
                            "deferred": buy_res.deferred,
                        }
                        stats = cast(dict[str, Any], res.get("stats") or {})
                    elif isinstance(buy_res, BaseException):
                        logger.error(f"gifts.autobuy failed: {type(buy_res).__name__}: {buy_res}")

                    if isinstance(notify_res, BaseException):
                        notify_error = (
                            "gifts.notify failed (thread): "
                            f"{type(notify_res).__name__}: {notify_res}"
                        )
                        logger.error(notify_error)
                    else:
                        sent = int(notify_res or 0)

                    try:
                        logger.info(
                            f"gifts.worker: FINAL purchased={len(res.get('purchased', []))} "
                            f"skipped={res.get('skipped')} notified={sent}"
                        )
                        for cid, st in (stats.get("channels") or {}).items():
                            ok = len(st.get("purchased", []))
                            fail = len(st.get("failed", []))
                            rsn = len(st.get("reasons", []))
                            chan_summary = (
                                "gifts.worker: FINAL channel="
                                f"{cid} ok={ok} fail={fail} reasons={rsn}"
                            )
                            logger.info(chan_summary)
                            if fail:
                                failed_details = (
                                    "gifts.worker: FINAL channel="
                                    f"{cid} failed_details={st.get('failed')}"
                                )
                                logger.info(failed_details)
                            if rsn:
                                reasons_details = (
                                    "gifts.worker: FINAL channel="
                                    f"{cid} reasons_details={st.get('reasons')}"
                                )
                                logger.info(reasons_details)

                        for aid, st in (stats.get("accounts") or {}).items():
                            account_summary = (
                                "gifts.worker: FINAL account="
                                f"{aid} spent={st.get('spent', 0)} "
                                f"start={st.get('balance_start', 0)} "
                                f"end={st.get('balance_end', 0)} buys={st.get('purchases', 0)}"
                            )
                            logger.info(account_summary)

                        gsk = stats.get("global_skips") or []
                        if gsk:
                            logger.info(
                                f"gifts.worker: FINAL global_skips n={len(gsk)} details={gsk}"
                            )
                    except Exception:
                        logger.exception("gifts.worker: final summary log failed")

            i = (i + 1) % n
            await asyncio.sleep(step)
    finally:
        try:
            await tg_shutdown(known_paths)
        finally:
            logger.info(f"gifts.worker: stop (user_id={uid})")


def _run_worker(uid: int) -> None:
    asyncio.run(_worker_async(uid))


def start_user_gifts(uid: int) -> None:
    if uid in GIFTS_THREADS:
        return
    state = _WorkerState(stop=threading.Event())
    GIFTS_THREADS[uid] = state
    th = threading.Thread(target=_run_worker, args=(uid,), daemon=True)
    state.thread = th
    th.start()


def stop_user_gifts(uid: int) -> None:
    state = GIFTS_THREADS.get(uid)
    if not state:
        return
    state.stop.set()
    GIFTS_THREADS.pop(uid, None)


def read_user_gifts(uid: int) -> list[dict[str, Any]]:
    _ensure_dir()
    return read_json_list_of_dicts(_gifts_path(uid))


def refresh_once(uid: int) -> list[dict[str, Any]]:
    _ensure_dir()
    db: Session = SessionLocal()
    try:
        acc = db.query(Account).filter(Account.user_id == uid).order_by(Account.id.asc()).first()
        if not acc:
            raise NoAccountsError("no_accounts")
        gifts = asyncio.run(
            _list_gifts_for_account_persist(
                acc.session_path, acc.api_profile.api_id, acc.api_profile.api_hash
            )
        )
        path = _gifts_path(uid)
        prev = read_json_list_of_dicts(path)
        merged = merge_new(prev, gifts)
        write_json_list(path, merged)
        gifts_event_bus.publish(
            uid, {"items": merged, "count": len(merged), "hash": hash_items(merged)}
        )
        return merged
    finally:
        db.close()
