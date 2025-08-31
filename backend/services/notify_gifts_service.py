# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio, os, hashlib, threading
from contextlib import closing
from typing import List, Dict, Tuple, Optional
import httpx
from sqlalchemy.orm import Session

from .tg_clients_service import tg_call
from ..db import SessionLocal
from ..models import User, UserSettings, Account
from ..logger import logger

_STICKERS_DIR = os.path.join(os.getenv("GIFTS_DIR", "gifts_data"), "stickers")

def _ensure_dir(p: str) -> None:
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass

def _collect_targets() -> List[Tuple[int, str, int]]:
    db: Session = SessionLocal()
    try:
        uids = [uid for (uid,) in db.query(User.id).filter(User.gifts_autorefresh == True).all()]
        out: List[Tuple[int, str, int]] = []
        for uid in uids:
            s = db.get(UserSettings, uid)
            token = (getattr(s, "bot_token", "") or "").strip() if s else ""
            chat = getattr(s, "notify_chat_id", None)
            if token and isinstance(chat, int):
                out.append((uid, token, int(chat)))
            else:
                if not token:
                    logger.warning(f"notify: uid={uid} has no bot_token")
                if chat is None:
                    logger.warning(f"notify: uid={uid} has no notify_chat_id")
        return out
    finally:
        db.close()

def _sticker_ext(mime: str | None) -> str:
    m = (mime or "").lower()
    if "tgsticker" in m: return ".tgs"
    if "webm" in m: return ".webm"
    if "webp" in m: return ".webp"
    return ".bin"

def _sticker_cache_path(g: Dict) -> Optional[str]:
    fid = str(g.get("sticker_file_id") or "").strip()
    if not fid:
        return None
    uniq = (g.get("sticker_unique_id") or "").strip()
    name = uniq if uniq else hashlib.md5(fid.encode("utf-8")).hexdigest()
    return os.path.join(_STICKERS_DIR, name + _sticker_ext(g.get("sticker_mime")))

async def _ensure_cached(http: httpx.AsyncClient, token: str, g: Dict) -> Optional[str]:
    path = _sticker_cache_path(g)
    if not path:
        return None
    _ensure_dir(_STICKERS_DIR)
    if os.path.isfile(path):
        return path
    base = f"https://api.telegram.org/bot{token}"
    fid = g.get("sticker_file_id")
    try:
        r = await http.post(f"{base}/getFile", json={"file_id": fid})
        logger.info(f"notify:req getFile url={base}/getFile json={{'file_id': {fid!r}}} -> code={r.status_code}")
        if r.status_code != 200 or not r.json().get("ok", False):
            logger.warning(f"notify:getFile fail code={r.status_code} body={r.text[:200]}")
            return None
        file_path = r.json()["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        got = await http.get(url)
        logger.info(f"notify:req file GET url={url} -> code={got.status_code} size={len(got.content) if got.content else 0}")
        if got.status_code != 200 or not got.content:
            logger.warning(f"notify:file dl fail code={got.status_code} size={len(got.content) if got.content else 0}")
            return None
        tmp = f"{path}.tmp"
        with open(tmp, "wb") as f:
            f.write(got.content)
        os.replace(tmp, path)
        logger.info(f"notify:cached {os.path.basename(path)}")
        return path
    except Exception:
        logger.exception("notify:cache error", exc_info=True)
        return None

async def _send_sticker(http: httpx.AsyncClient, token: str, chat: int, g: Dict) -> bool:
    path = await _ensure_cached(http, token, g)
    if not path:
        logger.warning(f"notify:no cache gift_id={g.get('id')}")
        return False
    base = f"https://api.telegram.org/bot{token}"
    mime = (
        "application/x-tgsticker" if path.endswith(".tgs")
        else "video/webm" if path.endswith(".webm")
        else "image/webp" if path.endswith(".webp")
        else "application/octet-stream"
    )
    try:
        with open(path, "rb") as f:
            blob = f.read()
        data = {"chat_id": str(int(chat)), "disable_notification": "true"}
        files = {"sticker": (os.path.basename(path), blob, mime)}
        logger.info(f"notify:req sendSticker url={base}/sendSticker data={data} file=({files['sticker'][0]}, {mime}, {len(blob)}B)")
        r = await http.post(f"{base}/sendSticker", data=data, files=files)
        ok = (r.status_code == 200 and r.json().get("ok", False))
        if not ok:
            logger.warning(f"notify:sendSticker fail code={r.status_code} body={r.text[:200]}")
        else:
            logger.info(f"notify:sticker ok chat={chat} gift_id={g.get('id')}")
        return ok
    except Exception:
        logger.exception("notify:sendSticker error", exc_info=True)
        return False

def _gift_text(g: Dict, chat: int) -> str:
    lim = bool(g.get("is_limited"))
    return (
        "Новый подарок\n"
        f"ID: {g.get('id')}\n"
        f"Цена: {g.get('price')}\n"
        f"Premium: {'да' if g.get('require_premium') else 'нет'}\n"
        f"Саплай: {g.get('total_amount') if lim else '∞'}\n"
        f"Доступно: {g.get('available_amount') if lim else '∞'}\n"
        f"Chat: {chat}"
    )

async def _notify_one(http: httpx.AsyncClient, uid: int, token: str, chat: int, g: Dict) -> None:
    base = f"https://api.telegram.org/bot{token}"
    try:
        chat = int(chat)
    except Exception:
        logger.warning(f"notify:bad chat uid={uid} chat={repr(chat)}")
        return
    logger.info(f"notify:start uid={uid} chat={chat} gift_id={g.get('id')}")
    try:
        await _send_sticker(http, token, chat, g)
    except Exception:
        logger.exception("notify:sticker pipeline", exc_info=True)
    try:
        payload = {"chat_id": chat, "text": _gift_text(g, chat), "disable_notification": True}
        logger.info(f"notify:req sendMessage url={base}/sendMessage json={payload}")
        r = await http.post(f"{base}/sendMessage", json=payload)
        if r.status_code != 200 or not r.json().get("ok", False):
            logger.warning(f"notify:sendMessage fail code={r.status_code} body={r.text[:200]}")
        else:
            logger.info(f"notify:text ok chat={chat} gift_id={g.get('id')}")
    except Exception:
        logger.exception("notify:text error", exc_info=True)
    await asyncio.sleep(0.04)

async def _collect_dm_ids(uids: List[int]) -> Dict[int, List[int]]:
    dm_ids_by_uid: Dict[int, List[int]] = {}
    with closing(SessionLocal()) as db:
        for uid in uids:
            ids: set[int] = set()
            accs = db.query(Account).filter(Account.user_id == uid).all()
            for a in accs:
                try:
                    me = await tg_call(a.session_path, a.api_profile.api_id, a.api_profile.api_hash, lambda c: c.get_me(), min_interval=0.5)
                    tid = int(getattr(me, "id", 0) or 0)
                    if tid > 0: ids.add(tid)
                except Exception:
                    logger.debug(f"notify:get_me fail acc_id={a.id}", exc_info=True)
                await asyncio.sleep(0.05)
            dm_ids_by_uid[uid] = sorted(ids)
            logger.info(f"notify:dm_ids uid={uid} count={len(dm_ids_by_uid[uid])}")
    return dm_ids_by_uid

async def broadcast_new_gifts(gifts: List[Dict]) -> int:
    if not gifts:
        return 0

    targets = _collect_targets()  # [(uid, token, notify_chat_id)]

    token_by_uid: Dict[int, str] = {}
    try:
        with closing(SessionLocal()) as db:
            rows = (
                db.query(User.id, UserSettings.bot_token)
                  .join(UserSettings, User.id == UserSettings.user_id)
                  .filter(User.gifts_autorefresh == True)
                  .all()
            )
            for uid, tok in rows:
                tok = (tok or "").strip()
                if tok:
                    token_by_uid[uid] = tok
    except Exception:
        logger.exception("notify:failed to fetch tokens from DB")

    uids = sorted({u for u, _, _ in targets} | set(token_by_uid.keys()))
    logger.info(f"notify:gifts={len(gifts)} targets={len(targets)} uids_for_dm={len(uids)}")

    dm_ids_by_uid: Dict[int, List[int]] = {}
    if uids:
        try:
            dm_ids_by_uid = await _collect_dm_ids(uids) or {}
        except Exception:
            logger.exception("notify:collect_dm_ids error")
            dm_ids_by_uid = {}

    sent = 0
    async with httpx.AsyncClient(timeout=30) as http:
        for uid, token, chat in targets:
            token = (token or token_by_uid.get(uid) or "").strip()
            if not token:
                logger.warning(f"notify:no token for uid={uid} (channel stage)")
                continue
            try:
                chat = int(chat)
            except Exception:
                logger.warning(f"notify:bad notify_chat_id uid={uid} chat={repr(chat)}")
                continue

            for g in gifts:
                try:
                    logger.info(f"notify:try (channel) uid={uid} chat={chat} gift_id={g.get('id')}")
                    await _notify_one(http, uid, token, chat, g)
                    sent += 1
                except Exception:
                    logger.exception(f"notify:channel send failed uid={uid} chat={chat} gift_id={g.get('id')}")
                await asyncio.sleep(0.12)

        for uid in uids:
            token = (token_by_uid.get(uid)
                     or next((t for (u, t, _) in targets if u == uid and t), "")
                    ).strip()
            if not token:
                logger.warning(f"notify:no token for uid={uid} (dm stage)")
                continue

            dm_ids = dm_ids_by_uid.get(uid) or []
            if not dm_ids:
                logger.warning(f"notify:no DM ids for uid={uid}")
                continue

            for user_chat_id in dm_ids:
                for g in gifts:
                    try:
                        logger.info(f"notify:try (dm) uid={uid} chat={user_chat_id} gift_id={g.get('id')}")
                        await _notify_one(http, uid, token, int(user_chat_id), g)
                        sent += 1
                    except Exception:
                        logger.exception(f"notify:dm send failed uid={uid} chat={user_chat_id} gift_id={g.get('id')}")
                    await asyncio.sleep(0.12)

    logger.info(f"notify:done sent={sent}")
    return sent



def broadcast_new_gifts_sync(gifts: List[Dict]) -> int:
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            out = {"n": 0, "e": None}
            def runner():
                try:
                    out["n"] = asyncio.run(broadcast_new_gifts(gifts))
                except Exception as e:
                    out["e"] = e
            t = threading.Thread(target=runner, daemon=True)
            t.start()
            t.join()
            if out["e"] is not None:
                raise out["e"]
            return int(out["n"])
    except RuntimeError:
        pass
    return asyncio.run(broadcast_new_gifts(gifts))
