# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio
import os, json, time, threading, hashlib, random
from collections import defaultdict
from queue import Queue
import sqlite3
from typing import Optional
from pyrogram import Client
from sqlalchemy.orm import Session, joinedload

from .notify_gifts_service import broadcast_new_gifts
from ..db import SessionLocal
from ..models import Account
from ..logger import logger

GIFTS_THREADS: dict[int, dict] = {}
_GIFTS_DIR = os.getenv("GIFTS_DIR", "gifts_data")
_CLIENTS: dict[str, dict[int, "_ClientBox"]] = {}
_CLIENTS_LOCK = threading.Lock()
_SESSION_LOCKS: dict[str, threading.Lock] = defaultdict(threading.Lock)
REFRESH_PERIOD = float(os.getenv("GIFTS_REFRESH_PERIOD", "15.0"))   # сек между циклами
ACC_TTL = float(os.getenv("GIFTS_ACCS_TTL", "60.0"))

class NoAccountsError(Exception): pass

def _gifts_path(uid:int)->str: return os.path.join(_GIFTS_DIR, f"user_{uid}.json")

def _ensure_dir()->None:
    try: os.makedirs(_GIFTS_DIR, exist_ok=True)
    except Exception: pass

def _merge_new(prev:list[dict], cur:list[dict])->list[dict]:
    by_id={x["id"]:x for x in prev}
    for x in cur: by_id[x["id"]]=x
    return sorted(by_id.values(), key=lambda x: (x.get("price",0), x["id"]))

def _read_json(path:str)->list[dict]:
    try:
        with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: return []

def _write_json(path:str, data:list[dict])->None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)

def _sleep(sec:float)->None:
    t=time.perf_counter()+sec
    while True:
        rem=t-time.perf_counter()
        if rem<=0: break
        time.sleep(min(rem,0.05))

def _hash_items(items:list[dict])->str:
    m=hashlib.md5()
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
        self._lock=threading.Lock()
        self._subs:dict[int,list[Queue]]={}
    def subscribe(self,user_id:int)->Queue:
        q:Queue=Queue()
        with self._lock: self._subs.setdefault(user_id,[]).append(q)
        return q
    def unsubscribe(self,user_id:int,q:Queue)->None:
        with self._lock:
            arr=self._subs.get(user_id,[])
            if q in arr: arr.remove(q)
            if not arr and user_id in self._subs: self._subs.pop(user_id,None)
    def publish(self,user_id:int,payload:dict)->None:
        with self._lock: arr=list(self._subs.get(user_id,[]))
        for q in arr:
            try: q.put_nowait(payload)
            except Exception: pass

gifts_event_bus=_GiftsEventBus()

# ---------- persistent clients ----------

class _ClientBox:
    def __init__(self, session_path:str, api_id:int, api_hash:str):
        self.session_path = os.path.abspath(session_path)
        self.api_id = api_id
        self.api_hash = api_hash
        self.client: Optional[Client] = None
        self.thread_id = threading.get_ident()
        self._loop = None
        self.init_lock: Optional[asyncio.Lock] = None
        self.call_lock: Optional[asyncio.Lock] = None
        self.last_call = 0.0

    def ensure_locks(self)->None:
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop = loop
            self.init_lock = asyncio.Lock()
            self.call_lock = asyncio.Lock()

async def _get_box(session_path:str, api_id:int, api_hash:str)->_ClientBox:
    key = os.path.abspath(session_path)
    tid = threading.get_ident()
    with _CLIENTS_LOCK:
        by_thread = _CLIENTS.setdefault(key, {})
        box = by_thread.get(tid)
        if not box:
            box = _ClientBox(key, api_id, api_hash)
            by_thread[tid] = box
    box.ensure_locks()
    async with box.init_lock:  # type: ignore[arg-type]
        if box.client is None or not getattr(box.client, "is_connected", False):
            # сериализация доступа к файлу сессии между потоками
            with _SESSION_LOCKS[key]:
                backoff = 0.2
                for attempt in range(6):
                    try:
                        box.client = Client(box.session_path, api_id=box.api_id, api_hash=box.api_hash, no_updates=True)
                        await box.client.start()
                        break
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e).lower() and attempt < 5:
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 2, 2.0)
                            continue
                        raise
    return box


async def _shutdown_clients(paths:set[str])->None:
    cur_tid = threading.get_ident()
    for p in list(paths):
        key = os.path.abspath(p)
        with _CLIENTS_LOCK:
            by_thread = _CLIENTS.get(key) or {}
            box = by_thread.get(cur_tid)
        if not box:
            continue
        try:
            with _SESSION_LOCKS[key]:
                if box.client:
                    backoff = 0.2
                    for attempt in range(6):
                        try:
                            await box.client.stop()
                            break
                        except sqlite3.OperationalError as e:
                            if "database is locked" in str(e).lower() and attempt < 5:
                                await asyncio.sleep(backoff)
                                backoff = min(backoff*2, 2.0)
                                continue
                            raise
        except Exception:
            pass
        finally:
            with _CLIENTS_LOCK:
                by_thread.pop(cur_tid, None)
                if not by_thread:
                    _CLIENTS.pop(key, None)


async def _list_gifts_for_account_persist(session_path:str, api_id:int, api_hash:str)->list[dict]:
    box=await _get_box(session_path, api_id, api_hash)
    rl=0.8
    backoff=0.4
    for attempt in range(5):
        try:
            async with box.call_lock:
                now=asyncio.get_running_loop().time()
                delay=max(0.0, box.last_call+rl-now)
                if delay>0: await asyncio.sleep(delay)
                gifts=await box.client.get_available_gifts()
                box.last_call=asyncio.get_running_loop().time()
            out=[]
            for g in gifts or []:
                out.append({
                    "id": int(getattr(g, "id", 0)),
                    "price": int(getattr(g, "price", 0)),
                    "is_limited": bool(getattr(g, "is_limited", False)),
                    "available_amount": int(getattr(g, "available_amount", 0)) if getattr(g, "is_limited",
                                                                                          False) else None,
                    "total_amount": (
                            getattr(g, "total_amount", None) or
                            getattr(getattr(g, "raw", None), "total_amount", None)
                    ),
                    "require_premium": bool(getattr(getattr(g, "raw", None), "require_premium", False)),
                    "sticker_file_id": getattr(getattr(g, "sticker", None), "file_id", None),
                    "sticker_unique_id": getattr(getattr(g, "sticker", None), "file_unique_id", None),
                    "sticker_mime": getattr(getattr(g, "sticker", None), "mime_type", None),
                })

            return out
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt<4:
                await asyncio.sleep(backoff); backoff*=2; continue
            raise
        except Exception:
            if attempt<4:
                await asyncio.sleep(backoff+random.random()*0.2)
                backoff=min(backoff*2,3.0); continue
            raise


# ---------- worker ----------

async def _worker_async(uid:int)->None:
    logger.info(f"gifts.worker: start (user_id={uid})")
    _ensure_dir()
    stop_evt=GIFTS_THREADS[uid]["stop"]
    known_paths:set[str]=set()
    accs:list[Account]=[]
    accs_loaded_at=0.0
    i=0
    merged_all=_read_json(_gifts_path(uid))
    last_hash=_hash_items(merged_all)
    try:
        while not stop_evt.is_set():
            now=time.monotonic()
            if not accs or (now-accs_loaded_at)>=ACC_TTL:
                db:Session=SessionLocal()
                try:
                    accs=(db.query(Account)
                          .options(joinedload(Account.api_profile))
                          .filter(Account.user_id==uid)
                          .order_by(Account.id.asc())
                          .all())
                    known_paths={a.session_path for a in accs}
                    accs_loaded_at=now
                    if i>=len(accs): i=0
                finally:
                    db.close()
                if not accs:
                    await asyncio.sleep(3.0)
                    continue
            n=len(accs)
            step=max(3.0/float(n),0.2)
            a=accs[i]
            try:
                disk_items = _read_json(_gifts_path(uid))
                prev_ids = {int(x.get("id", 0)) for x in disk_items if isinstance(x.get("id"), int)}

                gifts = await _list_gifts_for_account_persist(a.session_path, a.api_profile.api_id,
                                                              a.api_profile.api_hash)
                merged_all = _merge_new(disk_items or [], gifts)

                added = [g for g in merged_all if isinstance(g.get("id"), int) and g["id"] not in prev_ids]
            except Exception:
                logger.exception(f"gifts.worker: fetch failed (acc_id={a.id})")
                gifts = []
                added = []

            # лог итерации
            try:
                logger.info(
                    f"gifts.worker: iter user_id={uid} acc_id={a.id} "
                    f"gifts_now={len(gifts)} total_cached={len(merged_all)} new={len(added)}"
                )
            except Exception:
                pass

            new_hash=_hash_items(merged_all)
            if new_hash!=last_hash:
                last_hash=new_hash
                _write_json(_gifts_path(uid), merged_all)
                gifts_event_bus.publish(uid, {"items": merged_all, "count": len(merged_all), "hash": new_hash})
                if added:
                    try:
                        await broadcast_new_gifts(added)
                    except Exception:
                        logger.exception("gifts.notify failed")
            i=(i+1)%n
            await asyncio.sleep(step)
    finally:
        try:
            await _shutdown_clients(known_paths)
        finally:
            logger.info(f"gifts.worker: stop (user_id={uid})")


def _run_worker(uid:int)->None: asyncio.run(_worker_async(uid))

def start_user_gifts(uid:int)->None:
    if uid in GIFTS_THREADS: return
    d={"stop": threading.Event(), "th": None}
    GIFTS_THREADS[uid]=d
    th=threading.Thread(target=_run_worker, args=(uid,), daemon=True)
    d["th"]=th
    th.start()

def stop_user_gifts(uid:int)->None:
    d=GIFTS_THREADS.get(uid)
    if not d: return
    d["stop"].set()
    GIFTS_THREADS.pop(uid, None)

def read_user_gifts(uid:int)->list[dict]:
    _ensure_dir()
    return _read_json(_gifts_path(uid))

def refresh_once(uid:int)->list[dict]:
    _ensure_dir()
    db:Session=SessionLocal()
    try:
        acc=db.query(Account).filter(Account.user_id==uid).order_by(Account.id.asc()).first()
        if not acc: raise NoAccountsError("no_accounts")
        gifts=asyncio.run(_list_gifts_for_account_persist(acc.session_path, acc.api_profile.api_id, acc.api_profile.api_hash))
        path=_gifts_path(uid)
        prev=_read_json(path)
        merged=_merge_new(prev, gifts)
        _write_json(path, merged)
        gifts_event_bus.publish(uid, {"items": merged, "count": len(merged), "hash": _hash_items(merged)})
        return merged
    finally:
        db.close()
