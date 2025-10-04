# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio
import gzip
import hashlib
import json
import os
import shutil
import threading
import time
from collections import defaultdict
from pathlib import Path
from queue import Queue

import httpx
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from sqlalchemy.orm import Session

from ..auth import auth_required
from ..logger import logger
from ..models import User, UserSettings
from ..services.gifts_service import (
    NoAccountsError,
    gifts_event_bus,
    read_user_gifts,
    refresh_once,
    start_user_gifts,
    stop_user_gifts,
)

bp_gifts = Blueprint("gifts", __name__, url_prefix="/api")

_FILE_LOCKS: dict[str, threading.Lock] = defaultdict(threading.Lock)

def _cache_base_dir()->Path:
    base=current_app.config.get("GIFTS_CACHE_DIR")
    return Path(base) if base else Path(current_app.instance_path)/"gifts_cache"

def _shard_dir(key:str)->Path:
    shard=hashlib.sha1(key.encode("utf-8")).hexdigest()[:2]
    return _cache_base_dir()/shard

def _cached_path_for(key:str)->Path: return _shard_dir(key)/f"{key}.tgs"

def _find_cached_tgs(key:str)->Path|None:
    p=_cached_path_for(key)
    return p if p.exists() and p.stat().st_size>0 else None

def _save_atomic(path:Path, data:bytes)->None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    with open(tmp,"wb") as f:
        f.write(data); f.flush() 
        os.fsync(f.fileno())
    os.replace(tmp,path)

async def _botapi_download(file_id:str, token:str)->bytes:
    if not token: raise RuntimeError("no_bot_token")
    api=f"https://api.telegram.org/bot{token}"
    base=f"https://api.telegram.org/file/bot{token}"
    async with httpx.AsyncClient(timeout=30) as http:
        r=await http.get(f"{api}/getFile", params={"file_id":file_id})
        r.raise_for_status()
        p=r.json()
        if not (p.get("ok") and p.get("result") and p["result"].get("file_path")): raise RuntimeError("getFile error")
        fp=p["result"]["file_path"]
        r2=await http.get(f"{base}/{fp}", follow_redirects=True)
        r2.raise_for_status()
        return r2.content

def _run_async(coro)->bytes:
    try:
        loop=asyncio.get_running_loop()
        if loop.is_running():
            out:bytes|None=None
            err:Exception|None=None
            def _runner():
                nonlocal out,err
                try: out=asyncio.run(coro)
                except Exception as e: err=e
            t=threading.Thread(target=_runner, daemon=True)
            t.start()
            t.join()
            if err: raise err
            return out
    except RuntimeError:
        pass
    return asyncio.run(coro)

def _link_or_copy(src:Path, dst:Path)->None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except Exception:
        shutil.copy2(src, dst)

def _etag_for_path(p:Path)->str:
    st=p.stat()
    return f'W/"{int(st.st_mtime)}-{st.st_size}"'

def _send_lottie_json_from_tgs(path:Path)->Response:
    etag=_etag_for_path(path)
    inm=(request.headers.get("If-None-Match") or "").strip()
    if inm==etag:
        resp=Response(status=304)
        resp.headers["Cache-Control"]="public, max-age=31536000, immutable"
        resp.headers["ETag"]=etag
        return resp
    raw=path.read_bytes()
    try:
        data=gzip.decompress(raw)
    except Exception:
        return jsonify({"error":"bad_tgs"}),415
    resp=Response(data, mimetype="application/json")
    resp.headers["Cache-Control"]="public, max-age=31536000, immutable"
    resp.headers["ETag"]=etag
    resp.headers["X-Content-Type-Options"]="nosniff"
    return resp

def _promote_cached(src_key:str, dst_key:str)->Path|None:
    if src_key==dst_key: return _find_cached_tgs(dst_key)
    dst_lock=_FILE_LOCKS[dst_key]
    with dst_lock:
        dst=_find_cached_tgs(dst_key)
        if dst: return dst
        src=_find_cached_tgs(src_key)
        if not src: return None
        dst_path=_cached_path_for(dst_key)
        try:
            _link_or_copy(src, dst_path)
        except Exception:
            logger.exception("promote cache failed") 
            return None
        return dst_path

@bp_gifts.get("/gifts", endpoint="gifts_list")
@auth_required
def gifts_list(db:Session):
    return jsonify({"items": read_user_gifts(request.user_id)})

@bp_gifts.post("/gifts/refresh", endpoint="gifts_refresh")
@auth_required
def gifts_refresh(db:Session):
    want_stream = request.args.get("stream")=="1" or "application/x-ndjson" in (request.headers.get("Accept") or "")
    if not want_stream:
        try: return jsonify({"items": refresh_once(request.user_id)})
        except NoAccountsError: return jsonify({"error":"no_accounts"}),409
    def gen():
        def line(o:dict)->bytes: return (json.dumps(o, ensure_ascii=False)+"\n").encode("utf-8")
        yield line({"stage":"start"})
        try:
            items=refresh_once(request.user_id)
            yield line({"stage":"fetched","count":len(items)})
            yield line({"stage":"done","items":items})
        except NoAccountsError:
            yield line({"stage":"error","error":"no_accounts"})
        except Exception:
            logger.exception("gifts_refresh stream failed")
            yield line({"stage":"error","error":"internal"})
    resp=Response(stream_with_context(gen()), mimetype="application/x-ndjson")
    resp.headers["X-Accel-Buffering"]="no"
    return resp

@bp_gifts.get("/gifts/sticker.lottie", endpoint="gifts_sticker_lottie")
@auth_required
def gifts_sticker_lottie(db:Session):
    file_id=(request.args.get("file_id") or "").strip()
    uniq=(request.args.get("uniq") or "").strip()
    if not file_id and not uniq: return jsonify({"error":"file_id_or_uniq_required"}),400
    cache_key=uniq or file_id
    path=_find_cached_tgs(cache_key)
    if not path and uniq and file_id:
        path=_promote_cached(file_id, uniq)
    if not path and file_id:
        lock=_FILE_LOCKS[cache_key]
        with lock:
            path=_find_cached_tgs(cache_key)
            if not path:
                s=db.get(UserSettings, request.user_id)
                token=(getattr(s,"bot_token","") or "").strip()
                if not token: return jsonify({"error":"no_bot_token"}),409
                try:
                    data=_run_async(_botapi_download(file_id, token))
                    if not (len(data)>=2 and data[:2]==b"\x1f\x8b"): return jsonify({"error":"bad_tgs"}),415
                    target=_cached_path_for(cache_key)
                    _save_atomic(target, data)
                    path=target
                except Exception:
                    logger.exception("bot download failed")
                    return jsonify({"error":"download_failed"}),502
    if not path: return jsonify({"error":"download_failed"}),502
    return _send_lottie_json_from_tgs(path)

@bp_gifts.get("/gifts/settings", endpoint="gifts_settings")
@auth_required
def gifts_settings(db:Session):
    u=db.get(User, request.user_id)
    return jsonify({"auto_refresh": bool(getattr(u,"gifts_autorefresh",False))})

@bp_gifts.post("/gifts/settings", endpoint="gifts_settings_set")
@auth_required
def gifts_settings_set(db:Session):
    d=request.get_json(silent=True) or {}
    en=bool(d.get("auto_refresh"))
    u=db.get(User, request.user_id)
    u.gifts_autorefresh=en
    db.commit()
    if en: start_user_gifts(request.user_id)
    else: stop_user_gifts(request.user_id)
    return jsonify({"ok":True,"auto_refresh":en})

@bp_gifts.get("/gifts/stream", endpoint="gifts_stream")
@auth_required
def gifts_stream(db:Session):
    user_id=request.user_id
    def sse(event:str,data:dict)->bytes: return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
    q:Queue=gifts_event_bus.subscribe(user_id)
    @stream_with_context
    def gen():
        try:
            snap=read_user_gifts(user_id)
            yield sse("gifts", {"items":snap,"count":len(snap)})
            last_ping=time.monotonic()
            while True:
                try:
                    evt=q.get(timeout=10.0)
                    if evt and evt.get("items") is not None: yield sse("gifts", evt)
                except Exception: pass
                if time.monotonic()-last_ping>25:
                    yield b": ping\n\n" 
                    last_ping=time.monotonic()
        finally:
            gifts_event_bus.unsubscribe(user_id,q)
    return Response(gen(), headers={
        "Content-Type":"text/event-stream; charset=utf-8",
        "Cache-Control":"no-cache",
        "Connection":"keep-alive",
    })
