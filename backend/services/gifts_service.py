# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio
import os, json, time, threading, hashlib
from queue import Queue
from sqlalchemy.orm import Session, joinedload

from ..db import SessionLocal
from ..models import Account
from ..logger import logger
from .tg_clients_service import tg_call, tg_shutdown
from .autobuy_service import autobuy_new_gifts
from .notify_gifts_service import broadcast_new_gifts

GIFTS_THREADS: dict[int, dict] = {}
_GIFTS_DIR = os.getenv("GIFTS_DIR", "gifts_data")
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
    tmp = f"{path}.tmp"
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
            it.get("limited_per_user"),
            it.get("per_user_remains"),
            it.get("per_user_available"),
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

async def _list_gifts_for_account_persist(session_path:str, api_id:int, api_hash:str)->list[dict]:
    gifts = await tg_call(session_path, api_id, api_hash, lambda c: c.get_available_gifts(), min_interval=0.8)
    out=[]
    for g in gifts or []:
        raw = getattr(g, "raw", None)
        is_limited = bool(getattr(g, "is_limited", False))
        avail_total = int(getattr(g, "available_amount", 0)) if is_limited else None

        limited_per_user = bool(getattr(raw, "limited_per_user", False))
        per_user_remains = int(getattr(raw, "per_user_remains", 0)) if limited_per_user else None

        if limited_per_user:
            if isinstance(avail_total, int) and per_user_remains is not None:
                per_user_available = min(avail_total, per_user_remains)
            else:
                per_user_available = per_user_remains
        else:
            per_user_available = avail_total

        out.append({
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
        })
    return out


def _notify_run_blocking(items: list[dict]) -> int | Exception:
    try:
        return asyncio.run(broadcast_new_gifts(items))
    except Exception as e:
        try:
            logger.exception("gifts.notify failed in thread")
        except Exception:
            pass
        return e

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
            now=time.perf_counter()
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
            n=len(accs)
            if n == 0:
                await asyncio.sleep(1.0)
                continue
            step=max(3.0/float(n),0.2)
            a=accs[i]
            try:
                disk_items=_read_json(_gifts_path(uid))
                prev_ids={int(x.get("id",0)) for x in disk_items if isinstance(x.get("id"),int)}
                gifts=await _list_gifts_for_account_persist(a.session_path, a.api_profile.api_id, a.api_profile.api_hash)
                merged_all=_merge_new(disk_items or [], gifts)
                added=[g for g in merged_all if isinstance(g.get("id"),int) and g["id"] not in prev_ids]
            except Exception:
                logger.exception(f"gifts.worker: fetch failed (acc_id={a.id})")
                gifts=[]; added=[]
            try:
                logger.info(f"gifts.worker: iter user_id={uid} acc_id={a.id} gifts_now={len(gifts)} total_cached={len(merged_all)} new={len(added)}")
            except Exception:
                pass
            new_hash=_hash_items(merged_all)
            if new_hash!=last_hash:
                last_hash=new_hash
                _write_json(_gifts_path(uid), merged_all)
                gifts_event_bus.publish(uid, {"items": merged_all, "count": len(merged_all), "hash": new_hash})

                if added:
                    logger.info(f"gifts.worker: parallel start buy&notify items={len(added)}")

                    buy_task = asyncio.create_task(autobuy_new_gifts(uid, added))
                    notify_future = asyncio.to_thread(_notify_run_blocking, added)

                    res = {"purchased": [], "skipped": len(added), "stats": {}}
                    stats = {}
                    sent = 0

                    buy_res, notify_res = await asyncio.gather(buy_task, notify_future, return_exceptions=True)

                    if isinstance(buy_res, Exception):
                        logger.error(f"gifts.autobuy failed: {type(buy_res).__name__}: {buy_res}")
                    else:
                        res = buy_res or res
                        stats = res.get("stats") or {}

                    if isinstance(notify_res, Exception):
                        logger.error(f"gifts.notify failed (thread): {type(notify_res).__name__}: {notify_res}")
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
                            logger.info(f"gifts.worker: FINAL channel={cid} ok={ok} fail={fail} reasons={rsn}")
                            if fail:
                                logger.info(f"gifts.worker: FINAL channel={cid} failed_details={st.get('failed')}")
                            if rsn:
                                logger.info(f"gifts.worker: FINAL channel={cid} reasons_details={st.get('reasons')}")

                        for aid, st in (stats.get("accounts") or {}).items():
                            logger.info(
                                f"gifts.worker: FINAL account={aid} spent={st.get('spent', 0)} "
                                f"start={st.get('balance_start', 0)} end={st.get('balance_end', 0)} "
                                f"purchases={st.get('purchases', 0)}"
                            )

                        gsk = stats.get("global_skips") or []
                        if gsk:
                            logger.info(f"gifts.worker: FINAL global_skips n={len(gsk)} details={gsk}")
                    except Exception:
                        logger.exception("gifts.worker: final summary log failed")

            i = (i + 1) % n
            await asyncio.sleep(step)
    finally:
        try:
            await tg_shutdown(known_paths)
        finally:
            logger.info(f"gifts.worker: stop (user_id={uid})")

def _run_worker(uid:int) -> None:
    asyncio.run(_worker_async(uid))

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
