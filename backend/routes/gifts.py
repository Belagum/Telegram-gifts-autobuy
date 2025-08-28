# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import os
import json
import time
import gzip
import httpx
import asyncio
import threading
import hashlib
from pathlib import Path
from collections import defaultdict
from queue import Queue

from flask import (
    Blueprint, request, jsonify, current_app,
    Response, stream_with_context
)
from sqlalchemy.orm import Session

from ..auth import auth_required
from ..models import User
from ..logger import logger
from ..services.gifts_service import (
    start_user_gifts, stop_user_gifts,
    read_user_gifts, refresh_once,
    gifts_event_bus, NoAccountsError
)

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

def _save_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


async def _botapi_download(file_id: str, token: str) -> bytes:
    if not token:
        raise RuntimeError("no_bot_token")
    api_base  = f"https://api.telegram.org/bot{token}"
    file_base = f"https://api.telegram.org/file/bot{token}"
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(f"{api_base}/getFile", params={"file_id": file_id})
        r.raise_for_status()
        payload = r.json()
        if not (payload.get("ok") and payload.get("result") and payload["result"].get("file_path")):
            raise RuntimeError(f"getFile error: {payload}")
        file_path = payload["result"]["file_path"]
        r2 = await http.get(f"{file_base}/{file_path}", follow_redirects=True)
        r2.raise_for_status()
        return r2.content

def _ensure_cached_tgs(file_id: str, cache_key: str) -> Path | None:
    cached = _find_cached_tgs(cache_key)
    if cached: return cached
    lock = _FILE_LOCKS[cache_key]
    with lock:
        cached = _find_cached_tgs(cache_key)
        if cached: return cached
        try:
            data = asyncio.run(_botapi_download(file_id))
        except Exception:
            logger.exception("tgs download failed")
            return None
        if not (len(data) >= 2 and data[:2] == b"\x1f\x8b"):
            logger.error("not a .tgs (gzip) payload")
            return None
        target = _cached_path_for(cache_key)
        try:
            _save_atomic(target, data)
        except Exception:
            logger.exception("failed to save tgs cache")
            return None
        return target

def _promote_cached(src_key: str, dst_key: str) -> Path | None:
    if src_key == dst_key: return _find_cached_tgs(dst_key)
    dst_lock = _FILE_LOCKS[dst_key]
    with dst_lock:
        dst = _find_cached_tgs(dst_key)
        if dst: return dst
        src = _find_cached_tgs(src_key)
        if not src: return None
        dst_path = _cached_path_for(dst_key)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(src, dst_path)
        except Exception:
            logger.exception("promote cache failed")
            return None
        return dst_path

def _send_lottie_json_from_tgs(path: Path) -> Response:
    raw = path.read_bytes()
    try:
        data = gzip.decompress(raw)
    except Exception:
        return jsonify({"error": "bad_tgs"}), 415
    st = path.stat()
    etag = f'W/"{int(st.st_mtime)}-{st.st_size}"'
    resp = Response(data, mimetype="application/json")
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    resp.headers["ETag"] = etag
    return resp

# routes
@bp_gifts.get("/gifts", endpoint="gifts_list")
@auth_required
def gifts_list(db: Session):
    # фронт сам отфильтрует только tgs тут отдаём как есть
    return jsonify({"items": read_user_gifts(request.user_id)})

@bp_gifts.post("/gifts/refresh", endpoint="gifts_refresh")
@auth_required
def gifts_refresh(db: Session):
    want_stream = request.args.get("stream") == "1" or "application/x-ndjson" in (request.headers.get("Accept") or "")
    if not want_stream:
        try:
            return jsonify({"items": refresh_once(request.user_id)})
        except NoAccountsError:
            return jsonify({"error": "no_accounts"}), 409

    def gen():
        def line(obj: dict) -> bytes:
            return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        yield line({"stage": "start"})
        try:
            items = refresh_once(request.user_id)
            yield line({"stage": "fetched", "count": len(items)})
            yield line({"stage": "done", "items": items})
        except NoAccountsError:
            yield line({"stage": "error", "error": "no_accounts"})
        except Exception as e:
            logger.exception("gifts_refresh stream failed")
            yield line({"stage": "error", "error": "internal"})
    return Response(stream_with_context(gen()), mimetype="application/x-ndjson")


@bp_gifts.get("/gifts/sticker.lottie", endpoint="gifts_sticker_lottie")
@auth_required
def gifts_sticker_lottie(db: Session):
  from ..models import UserSettings
  file_id = (request.args.get("file_id") or "").strip()
  uniq    = (request.args.get("uniq") or "").strip()
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
        s = db.get(UserSettings, request.user_id)
        token = (getattr(s, "bot_token", "") or "").strip()
        if not token:
          return jsonify({"error":"no_bot_token"}), 409
        async def _dl(tok:str, fid:str)->bytes:
          api = f"https://api.telegram.org/bot{tok}"
          base= f"https://api.telegram.org/file/bot{tok}"
          async with httpx.AsyncClient(timeout=30) as http:
            r = await http.get(f"{api}/getFile", params={"file_id": fid}); r.raise_for_status()
            p = r.json()
            if not p.get("ok"): raise RuntimeError("getFile failed")
            fp = p["result"]["file_path"]
            r2 = await http.get(f"{base}/{fp}", follow_redirects=True); r2.raise_for_status()
            return r2.content
        try:
          data = asyncio.run(_dl(token, file_id))
          if not (len(data)>=2 and data[:2]==b"\x1f\x8b"):
            return jsonify({"error":"bad_tgs"}), 415
          target = _cached_path_for(cache_key)
          _save_atomic(target, data)
          path = target
        except Exception:
          logger.exception("bot download failed")
          return jsonify({"error":"download_failed"}), 502

  if not path:
    return jsonify({"error":"download_failed"}), 502
  return _send_lottie_json_from_tgs(path)


@bp_gifts.get("/gifts/settings", endpoint="gifts_settings")
@auth_required
def gifts_settings(db: Session):
    u = db.get(User, request.user_id)
    return jsonify({"auto_refresh": bool(getattr(u, "gifts_autorefresh", False))})

@bp_gifts.post("/gifts/settings", endpoint="gifts_settings_set")
@auth_required
def gifts_settings_set(db: Session):
    d = request.get_json(silent=True) or {}
    en = bool(d.get("auto_refresh"))
    u = db.get(User, request.user_id)
    u.gifts_autorefresh = en
    db.commit()
    if en: start_user_gifts(request.user_id)
    else:  stop_user_gifts(request.user_id)
    return jsonify({"ok": True, "auto_refresh": en})

@bp_gifts.get("/gifts/stream", endpoint="gifts_stream")
@auth_required
def gifts_stream(db: Session):
    """SSE: стримим обновления gifts_event_bus в реальном времени."""
    user_id = request.user_id
    def sse(event: str, data: dict) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
    q: Queue = gifts_event_bus.subscribe(user_id)

    @stream_with_context
    def gen():
        try:
            snap = read_user_gifts(user_id)
            yield sse("gifts", {"items": snap, "count": len(snap)})
            last_ping = time.monotonic()
            while True:
                try:
                    evt = q.get(timeout=10.0)
                    if evt and evt.get("items") is not None:
                        yield sse("gifts", evt)
                except Exception:
                    pass
                if time.monotonic() - last_ping > 25:
                    yield b": ping\n\n"; last_ping = time.monotonic()
        finally:
            gifts_event_bus.unsubscribe(user_id, q)

    return Response(gen(), headers={
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    })
