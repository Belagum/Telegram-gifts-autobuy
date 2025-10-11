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

from backend.infrastructure.db import SessionLocal
from backend.infrastructure.db.models import Account
from backend.services.autobuy_service import autobuy_new_gifts
from backend.services.notify_gifts_service import broadcast_new_gifts
from backend.services.tg_clients_service import tg_call, tg_shutdown
from backend.shared.logging import logger
from backend.shared.utils.gifts_utils import hash_items, merge_new
from backend.shared.utils.jsonio import read_json_list_of_dicts, write_json_list


@dataclass
class _WorkerState:
    stop: threading.Event
    thread: threading.Thread | None = None


GIFTS_THREADS: dict[int, _WorkerState] = {}
_DEFERRED_TASKS: dict[int, dict[tuple[int, int], asyncio.Task[Any]]] = {}
_GIFTS_DIR = os.getenv("GIFTS_DIR", "gifts_data")
ACC_TTL = float(os.getenv("GIFTS_ACCS_TTL", "60.0"))


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


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


def _cancel_deferred_runs(uid: int) -> None:
    tasks = _DEFERRED_TASKS.pop(uid, {})
    for task in tasks.values():
        task.cancel()


def _schedule_deferred_runs(uid: int, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    tasks = _DEFERRED_TASKS.setdefault(uid, {})
    for row in rows:
        gift_id = int(row.get("gift_id", 0))
        account_id = int(row.get("account_id", 0))
        run_at_raw = row.get("run_at")
        if gift_id <= 0 or account_id <= 0 or not isinstance(run_at_raw, str):
            continue
        run_at = _parse_iso_datetime(run_at_raw)
        if run_at is None:
            continue
        key = (gift_id, account_id)
        existing = tasks.get(key)
        if existing and not existing.done():
            existing.cancel()
        task = asyncio.create_task(_run_deferred_autobuy(uid, gift_id, account_id, run_at))
        tasks[key] = task
        try:
            logger.info(
                f"gifts.worker: scheduled deferred user_id={uid} gift_id={gift_id} "
                f"acc_id={account_id} run_at={run_at_raw}"
            )
        except Exception:
            pass


async def _run_deferred_autobuy(uid: int, gift_id: int, account_id: int, run_at: datetime) -> None:
    key = (gift_id, account_id)
    try:
        delay = max((run_at - datetime.now(UTC)).total_seconds(), 0.0)
        if delay > 0:
            await asyncio.sleep(delay)
        items = read_json_list_of_dicts(_gifts_path(uid))
        gift = next(
            (g for g in items if isinstance(g.get("id"), int) and int(g.get("id", 0)) == gift_id),
            None,
        )
        if not gift:
            logger.info(
                f"gifts.worker: deferred skip user_id={uid} gift_id={gift_id} reason=not_found"
            )
            return
        logger.info(
            f"gifts.worker: deferred trigger user_id={uid} gift_id={gift_id} acc_id={account_id}"
        )
        await autobuy_new_gifts(uid, [gift])
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            f"gifts.worker: deferred run failed user_id={uid} gift_id={gift_id} acc_id={account_id}"
        )
    finally:
        tasks = _DEFERRED_TASKS.get(uid)
        if tasks is not None:
            task = tasks.pop(key, None)
            if task is not None and task is not asyncio.current_task():
                task.cancel()


async def _list_gifts_for_account_persist(
    account_id: int, session_path: str, api_id: int, api_hash: str
) -> list[dict[str, Any]]:
    gifts = cast(
        list[Any],
        await tg_call(
            session_path, api_id, api_hash, lambda c: c.get_available_gifts(), min_interval=0.8
        ),
    )
    out: list[dict[str, Any]] = []
    for g in gifts or []:
        raw = getattr(g, "raw", None)
        is_limited = bool(getattr(g, "is_limited", False))
        avail_total: int | None = int(getattr(g, "available_amount", 0)) if is_limited else None

        limited_per_user = bool(getattr(raw, "limited_per_user", False))
        per_user_remains: int | None = (
            int(getattr(raw, "per_user_remains", 0)) if limited_per_user else None
        )

        if limited_per_user:
            if isinstance(avail_total, int) and per_user_remains is not None:
                per_user_available: int | None = min(avail_total, per_user_remains)
            else:
                per_user_available = per_user_remains
        else:
            per_user_available = avail_total

        def _to_iso_utc(value: Any) -> str | None:
            try:
                if value is None:
                    return None
                if isinstance(value, int | float):
                    dt = datetime.fromtimestamp(int(value), tz=UTC)
                    return dt.isoformat().replace("+00:00", "Z")
                if isinstance(value, datetime):
                    dt = value if value.tzinfo else value.replace(tzinfo=UTC)
                    dt = dt.astimezone(UTC)
                    return dt.isoformat().replace("+00:00", "Z")
                if isinstance(value, str):
                    s = value.strip()
                    if s:
                        return s
                ts = getattr(value, "timestamp", None)
                if callable(ts):
                    return _to_iso_utc(ts())
            except Exception:
                return None
            return None

        locked_raw = (
            getattr(g, "locked_until_date", None)
            or getattr(raw, "locked_until_date", None)
            or getattr(g, "locked_until", None)
            or getattr(raw, "locked_until", None)
        )
        locked_until_date = _to_iso_utc(locked_raw)

        item = {
            "id": int(getattr(g, "id", 0)),
            "price": int(getattr(g, "price", 0)),
            "is_limited": is_limited,
            "available_amount": avail_total,
            "total_amount": getattr(g, "total_amount", None) or getattr(raw, "total_amount", None),
            "require_premium": bool(getattr(raw, "require_premium", False)),
            "limited_per_user": limited_per_user,
            "per_user_remains": per_user_remains,
            "per_user_available": per_user_available,
            "sticker_file_id": getattr(getattr(g, "sticker", None), "file_id", None),
            "sticker_unique_id": getattr(getattr(g, "sticker", None), "file_unique_id", None),
            "sticker_mime": getattr(getattr(g, "sticker", None), "mime_type", None),
        }
        locks = {str(account_id): locked_until_date}
        item["locks"] = locks
        out.append(item)
    return out


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
                    a.id, a.session_path, a.api_profile.api_id, a.api_profile.api_hash
                )
                merged_all = merge_new(disk_items or [], gifts)
                added_ids = {
                    int(g.get("id", 0))
                    for g in merged_all
                    if isinstance(g.get("id"), int) and int(g.get("id", 0)) not in prev_ids
                }
                added = []
                if added_ids:
                    for extra in accs:
                        if extra.id == a.id:
                            continue
                        extra_gifts = await _list_gifts_for_account_persist(
                            extra.id,
                            extra.session_path,
                            extra.api_profile.api_id,
                            extra.api_profile.api_hash,
                        )
                        merged_all = merge_new(merged_all, extra_gifts)
                    added = [
                        g
                        for g in merged_all
                        if isinstance(g.get("id"), int) and int(g.get("id", 0)) in added_ids
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

                    buy_task = asyncio.create_task(autobuy_new_gifts(uid, added))
                    notify_future = asyncio.to_thread(_notify_run_blocking, added)

                    res: dict[str, Any] = {"purchased": [], "skipped": len(added), "stats": {}}
                    stats: dict[str, Any] = {}
                    sent = 0

                    buy_res, notify_res = await asyncio.gather(
                        buy_task, notify_future, return_exceptions=True
                    )

                    if isinstance(buy_res, Exception):
                        logger.error(f"gifts.autobuy failed: {type(buy_res).__name__}: {buy_res}")
                    else:
                        res = cast(dict[str, Any], buy_res or res)
                        stats = cast(dict[str, Any], res.get("stats") or {})
                        deferred_rows = cast(list[dict[str, Any]], res.get("deferred") or [])
                        if not deferred_rows and stats:
                            deferred_rows = cast(list[dict[str, Any]], stats.get("deferred") or [])
                        if deferred_rows:
                            _schedule_deferred_runs(uid, deferred_rows)

                    if isinstance(notify_res, Exception):
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
        _cancel_deferred_runs(uid)
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
    _cancel_deferred_runs(uid)
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
                acc.id, acc.session_path, acc.api_profile.api_id, acc.api_profile.api_hash
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
