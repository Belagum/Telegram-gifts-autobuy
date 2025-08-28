# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio
import os, json, time, threading, hashlib
from queue import Queue

from pyrogram import Client
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Account
from ..logger import logger

_GIFTS_THREADS: dict[int, dict] = {}
_GIFTS_DIR = os.getenv("GIFTS_DIR", "gifts_data")

class NoAccountsError(Exception): pass

def _gifts_path(uid:int)->str:
    return os.path.join(_GIFTS_DIR, f"user_{uid}.json")

def _ensure_dir()->None:
    try:
        os.makedirs(_GIFTS_DIR, exist_ok=True)
    except Exception:
        pass

async def _list_gifts_for_account(session_path: str, api_id: int, api_hash: str) -> list[dict]:
    async with Client(session_path, api_id=api_id, api_hash=api_hash, no_updates=True) as c:
        gifts = await c.get_available_gifts()
        out = []
        for g in gifts or []:
            st = getattr(g, "sticker", None)
            out.append({
                "id": int(getattr(g, "id", 0)),
                "price": int(getattr(g, "price", 0)),
                "is_limited": bool(getattr(g, "is_limited", False)),
                "available_amount": int(getattr(g, "available_amount", 0)) if getattr(g, "is_limited", False) else None,
                "require_premium": bool(getattr(getattr(g, "raw", None), "require_premium", False)),
                "sticker_file_id": getattr(st, "file_id", None),
                "sticker_unique_id": getattr(st, "file_unique_id", None),
                "sticker_mime": getattr(st, "mime_type", None),
            })
        return out

def _merge_new(prev:list[dict], cur:list[dict])->list[dict]:
    by_id={x["id"]:x for x in prev}
    for x in cur:
        by_id[x["id"]]=x
    return sorted(by_id.values(), key=lambda x: (x.get("price", 0), x["id"]))

def _read_json(path:str)->list[dict]:
    try:
        with open(path,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _write_json(path:str, data:list[dict])->None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)

def _sleep(sec:float)->None:
    t=time.perf_counter()+sec
    while True:
        rem=t-time.perf_counter()
        if rem<=0: break
        time.sleep(min(rem,0.05))

def _hash_items(items: list[dict]) -> str:
    m = hashlib.md5()
    for it in items:
        m.update(str((
            it.get("id"),
            it.get("price"),
            it.get("is_limited"),
            it.get("available_amount"),
            it.get("require_premium"),
            it.get("sticker_file_id"),
            it.get("sticker_mime"),
        )).encode("utf-8"))
    return m.hexdigest()

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

    def publish(self, user_id: int, payload: dict) -> None:
        with self._lock:
            arr = list(self._subs.get(user_id, []))
        for q in arr:
            try:
                q.put_nowait(payload)
            except Exception:
                pass

gifts_event_bus = _GiftsEventBus()

def _worker(uid:int)->None:
    logger.info(f"gifts.worker: start (user_id={uid})")
    _ensure_dir()
    stop_evt=_GIFTS_THREADS[uid]["stop"]
    last_hash: str | None = None

    while not stop_evt.is_set():
        db:Session=SessionLocal()
        try:
            accs=db.query(Account).filter(Account.user_id==uid).order_by(Account.id.asc()).all()
            if not accs:
                _sleep(3.0)
                continue

            n=max(1,len(accs))
            step=max(3.0/float(n),0.2)

            merged_all: list[dict] = _read_json(_gifts_path(uid))
            for a in accs:
                if stop_evt.is_set(): break
                try:
                    gifts=asyncio.run(_list_gifts_for_account(a.session_path, a.api_profile.api_id, a.api_profile.api_hash))
                    merged_all=_merge_new(merged_all,gifts)
                except Exception:
                    logger.exception(f"gifts.worker: fetch failed (acc_id={a.id})")
                _sleep(step)

            path=_gifts_path(uid)
            _write_json(path, merged_all)

            new_hash = _hash_items(merged_all)
            if new_hash != last_hash:
                last_hash = new_hash
                gifts_event_bus.publish(uid, {"items": merged_all, "count": len(merged_all), "hash": new_hash})

        except Exception:
            logger.exception(f"gifts.worker: loop error (user_id={uid})")
            _sleep(1.5)
        finally:
            db.close()

    logger.info(f"gifts.worker: stop (user_id={uid})")

def start_user_gifts(uid:int)->None:
    if uid in _GIFTS_THREADS: return
    d={"stop": threading.Event(), "th": None}
    _GIFTS_THREADS[uid]=d
    th=threading.Thread(target=_worker, args=(uid,), daemon=True)
    d["th"]=th
    th.start()

def stop_user_gifts(uid:int)->None:
    d=_GIFTS_THREADS.get(uid)
    if not d: return
    d["stop"].set()
    _GIFTS_THREADS.pop(uid, None)

def read_user_gifts(uid:int)->list[dict]:
    _ensure_dir()
    return _read_json(_gifts_path(uid))

def refresh_once(uid:int)->list[dict]:
    _ensure_dir()
    db:Session=SessionLocal()
    try:
        acc = db.query(Account).filter(Account.user_id==uid).order_by(Account.id.asc()).first()
        if not acc:
            raise NoAccountsError("no_accounts")
        gifts = asyncio.run(_list_gifts_for_account(acc.session_path, acc.api_profile.api_id, acc.api_profile.api_hash))
        path = _gifts_path(uid)
        prev = _read_json(path)
        merged = _merge_new(prev, gifts)
        _write_json(path, merged)
        gifts_event_bus.publish(uid, {"items": merged, "count": len(merged), "hash": _hash_items(merged)})
        return merged
    finally:
        db.close()
