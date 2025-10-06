# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio
import hashlib
import os
import threading
from contextlib import closing
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..logger import logger
from ..models import Account, User, UserSettings
from .tg_clients_service import tg_call

_STICKERS_DIR = os.path.join(os.getenv("GIFTS_DIR", "gifts_data"), "stickers")


def _ensure_dir(p: str) -> None:
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass


def _collect_targets() -> list[tuple[int, str, int]]:
    db: Session = SessionLocal()
    try:
        uids = [uid for (uid,) in db.query(User.id).filter(User.gifts_autorefresh).all()]
        out: list[tuple[int, str, int]] = []
        for uid in uids:
            s = db.get(UserSettings, uid)
            token = (getattr(s, "bot_token", "") or "").strip() if s else ""
            chat = getattr(s, "notify_chat_id", None)
            if token and isinstance(chat, int):
                out.append((uid, token, int(chat)))
            else:
                if not token:
                    logger.warning("notify: uid=%s has no bot_token", uid)
                if chat is None:
                    logger.warning("notify: uid=%s has no notify_chat_id", uid)
        return out
    finally:
        db.close()


def _sticker_ext(mime: str | None) -> str:
    m = (mime or "").lower()
    if "tgsticker" in m:
        return ".tgs"
    if "webm" in m:
        return ".webm"
    if "webp" in m:
        return ".webp"
    return ".bin"


def _sticker_cache_path(g: dict) -> str | None:
    fid = str(g.get("sticker_file_id") or "").strip()
    if not fid:
        return None
    uniq = (g.get("sticker_unique_id") or "").strip()
    name = uniq if uniq else hashlib.md5(fid.encode("utf-8")).hexdigest()
    return os.path.join(_STICKERS_DIR, name + _sticker_ext(g.get("sticker_mime")))


async def _ensure_cached(http: httpx.AsyncClient, token: str, g: dict) -> str | None:
    path = _sticker_cache_path(g)
    if not path:
        return None
    _ensure_dir(_STICKERS_DIR)
    if os.path.isfile(path):
        return path
    base = f"https://api.telegram.org/bot{token}"
    fid = g.get("sticker_file_id")
    try:
        get_file_url = f"{base}/getFile"
        payload = {"file_id": fid}
        r = await http.post(get_file_url, json=payload)
        logger.info(
            "notify:req getFile url=%s json=%s -> code=%s",
            get_file_url,
            payload,
            r.status_code,
        )
        if r.status_code != 200 or not r.json().get("ok", False):
            logger.warning(
                "notify:getFile fail code=%s body=%s",
                r.status_code,
                r.text[:200],
            )
            return None
        file_path = r.json()["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        got = await http.get(url)
        size = len(got.content) if got.content else 0
        logger.info(
            "notify:req file GET url=%s -> code=%s size=%s",
            url,
            got.status_code,
            size,
        )
        if got.status_code != 200 or not got.content:
            logger.warning(
                "notify:file dl fail code=%s size=%s",
                got.status_code,
                size,
            )
            return None
        tmp = f"{path}.tmp"
        with open(tmp, "wb") as f:
            f.write(got.content)
        os.replace(tmp, path)
        logger.info("notify:cached %s", os.path.basename(path))
        return path
    except Exception:
        logger.exception("notify:cache error", exc_info=True)
        return None


async def _send_sticker(http: httpx.AsyncClient, token: str, chat: int, g: dict) -> bool:
    path = await _ensure_cached(http, token, g)
    if not path:
        logger.warning(f"notify:no cache gift_id={g.get('id')}")
        return False
    base = f"https://api.telegram.org/bot{token}"
    mime = (
        "application/x-tgsticker"
        if path.endswith(".tgs")
        else "video/webm"
        if path.endswith(".webm")
        else "image/webp"
        if path.endswith(".webp")
        else "application/octet-stream"
    )
    try:
        with open(path, "rb") as f:
            blob = f.read()
        data = {"chat_id": str(int(chat)), "disable_notification": "true"}
        sticker_name = os.path.basename(path)
        files = {"sticker": (sticker_name, blob, mime)}
        send_url = f"{base}/sendSticker"
        logger.info(
            "notify:req sendSticker url=%s data=%s file=(%s, %s, %sB)",
            send_url,
            data,
            sticker_name,
            mime,
            len(blob),
        )
        r = await http.post(send_url, data=data, files=files)
        ok = r.status_code == 200 and r.json().get("ok", False)
        if not ok:
            logger.warning(
                "notify:sendSticker fail code=%s body=%s",
                r.status_code,
                r.text[:200],
            )
        else:
            logger.info("notify:sticker ok chat=%s gift_id=%s", chat, g.get("id"))
        return ok
    except Exception:
        logger.exception("notify:sendSticker error", exc_info=True)
        return False


def _gift_text(g: dict, chat: int) -> str:
    lim = bool(g.get("is_limited"))
    avail_val = g.get("available_amount")
    avail_total = avail_val if lim and isinstance(avail_val, int) else None
    lpu = bool(g.get("limited_per_user"))
    pu_rem_raw = g.get("per_user_remains")
    pu_rem = pu_rem_raw if isinstance(pu_rem_raw, int) else None
    pu_av_raw = g.get("per_user_available")
    pu_av = pu_av_raw if isinstance(pu_av_raw, int) else None
    if pu_av is None:
        a = avail_total if isinstance(avail_total, int) else None
        r = pu_rem if isinstance(pu_rem, int) else None
        pu_av = (
            (min(a, r) if (a is not None and r is not None) else (r if r is not None else a))
            if lpu
            else (avail_total if lim else None)
        )

    lines = [
        "Новый подарок",
        f"ID: {g.get('id')}",
        f"Цена: {g.get('price')}",
        f"Premium: {'да' if g.get('require_premium') else 'нет'}",
        f"Саплай: {g.get('total_amount') if lim else '∞'}",
        f"Доступно: {avail_total if lim else '∞'}",
    ]
    if lpu:
        remaining = pu_rem if pu_rem is not None else "—"
        available = pu_av if pu_av is not None else "—"
        lines.append(f"Лимит на пользователя: остаток={remaining} доступно={available}")
    else:
        lines.append("Лимит на пользователя: безлимитно к пользователям")
    lines.append(f"Chat: {chat}")
    return "\n".join(lines)


async def _notify_one(http: httpx.AsyncClient, uid: int, token: str, chat: int, g: dict) -> None:
    base = f"https://api.telegram.org/bot{token}"
    try:
        chat = int(chat)
    except Exception:
        logger.warning("notify:bad chat uid=%s chat=%r", uid, chat)
        return
    logger.info("notify:start uid=%s chat=%s gift_id=%s", uid, chat, g.get("id"))
    try:
        await _send_sticker(http, token, chat, g)
    except Exception:
        logger.exception("notify:sticker pipeline", exc_info=True)
    try:
        payload = {"chat_id": chat, "text": _gift_text(g, chat), "disable_notification": True}
        send_msg_url = f"{base}/sendMessage"
        logger.info(
            "notify:req sendMessage url=%s json=%s",
            send_msg_url,
            payload,
        )
        r = await http.post(send_msg_url, json=payload)
        if r.status_code != 200 or not r.json().get("ok", False):
            logger.warning(
                "notify:sendMessage fail code=%s body=%s",
                r.status_code,
                r.text[:200],
            )
        else:
            logger.info("notify:text ok chat=%s gift_id=%s", chat, g.get("id"))
    except Exception:
        logger.exception("notify:text error", exc_info=True)
    await asyncio.sleep(0.04)


async def _collect_dm_ids(uids: list[int]) -> dict[int, list[int]]:
    dm_ids_by_uid: dict[int, list[int]] = {}
    with closing(SessionLocal()) as db:
        for uid in uids:
            ids: set[int] = set()
            accs = db.query(Account).filter(Account.user_id == uid).all()
            for a in accs:
                try:
                    me = await tg_call(
                        a.session_path,
                        a.api_profile.api_id,
                        a.api_profile.api_hash,
                        lambda c: c.get_me(),
                        min_interval=0.5,
                    )
                    tid = int(getattr(me, "id", 0) or 0)
                    if tid > 0:
                        ids.add(tid)
                except Exception:
                    logger.debug("notify:get_me fail acc_id=%s", a.id, exc_info=True)
                await asyncio.sleep(0.05)
            dm_ids_by_uid[uid] = sorted(ids)
            logger.info(
                "notify:dm_ids uid=%s count=%s",
                uid,
                len(dm_ids_by_uid[uid]),
            )
    return dm_ids_by_uid


async def broadcast_new_gifts(gifts: list[dict]) -> int:
    if not gifts:
        return 0

    targets = _collect_targets()  # [(uid, token, notify_chat_id)]

    token_by_uid: dict[int, str] = {}
    try:
        with closing(SessionLocal()) as db:
            rows = (
                db.query(User.id, UserSettings.bot_token)
                .join(UserSettings, User.id == UserSettings.user_id)
                .filter(User.gifts_autorefresh)
                .all()
            )
            for uid, tok in rows:
                tok = (tok or "").strip()
                if tok:
                    token_by_uid[uid] = tok
    except Exception:
        logger.exception("notify:failed to fetch tokens from DB")

    uids = sorted({u for u, _, _ in targets} | set(token_by_uid.keys()))
    logger.info(
        "notify:gifts=%s targets=%s uids_for_dm=%s",
        len(gifts),
        len(targets),
        len(uids),
    )

    dm_ids_by_uid: dict[int, list[int]] = {}
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
                logger.warning("notify:no token for uid=%s (channel stage)", uid)
                continue
            try:
                chat = int(chat)
            except Exception:
                logger.warning("notify:bad notify_chat_id uid=%s chat=%r", uid, chat)
                continue

            for g in gifts:
                try:
                    logger.info(
                        "notify:try (channel) uid=%s chat=%s gift_id=%s",
                        uid,
                        chat,
                        g.get("id"),
                    )
                    await _notify_one(http, uid, token, chat, g)
                    sent += 1
                except Exception:
                    logger.exception(
                        "notify:channel send failed uid=%s chat=%s gift_id=%s",
                        uid,
                        chat,
                        g.get("id"),
                    )
                await asyncio.sleep(0.12)

        for uid in uids:
            token = (
                token_by_uid.get(uid) or next((t for (u, t, _) in targets if u == uid and t), "")
            ).strip()
            if not token:
                logger.warning("notify:no token for uid=%s (dm stage)", uid)
                continue

            dm_ids = dm_ids_by_uid.get(uid) or []
            if not dm_ids:
                logger.warning("notify:no DM ids for uid=%s", uid)
                continue

            for user_chat_id in dm_ids:
                for g in gifts:
                    try:
                        logger.info(
                            "notify:try (dm) uid=%s chat=%s gift_id=%s",
                            uid,
                            user_chat_id,
                            g.get("id"),
                        )
                        await _notify_one(http, uid, token, user_chat_id, g)
                        sent += 1
                    except Exception:
                        logger.exception(
                            "notify:dm send failed uid=%s chat=%s gift_id=%s",
                            uid,
                            user_chat_id,
                            g.get("id"),
                        )
                    await asyncio.sleep(0.12)

    logger.info("notify:done sent=%s", sent)
    return sent


def broadcast_new_gifts_sync(gifts: list[dict[str, Any]]) -> int:
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            result_n = 0
            result_err: Exception | None = None

            def runner() -> None:
                nonlocal result_n, result_err
                try:
                    result_n = asyncio.run(broadcast_new_gifts(gifts))
                except Exception as exc:
                    result_err = exc

            t = threading.Thread(target=runner, daemon=True)
            t.start()
            t.join()
            if result_err is not None:
                raise result_err
            return result_n
    except RuntimeError:
        pass
    return asyncio.run(broadcast_new_gifts(gifts))
