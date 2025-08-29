# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio, threading
from typing import List, Dict, Tuple
import httpx
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import User, UserSettings, Account
from ..logger import logger

def _collect_targets()->List[Tuple[str,List[int]]]:
    db: Session = SessionLocal()
    try:
        uids=[uid for (uid,) in db.query(User.id).filter(User.gifts_autorefresh==True).all()]
        out: List[Tuple[str,List[int]]] = []
        for uid in uids:
            s=db.get(UserSettings, uid)
            token=(getattr(s,"bot_token","") or "").strip() if s else ""
            if not token: continue
            acc_ids=[int(aid) for (aid,) in db.query(Account.id).filter(Account.user_id==uid).all()]
            if acc_ids: out.append((token, acc_ids))
        return out
    finally:
        db.close()

async def _notify_one(http, token: str, chat: int, g: Dict) -> None:
    base = f"https://api.telegram.org/bot{token}"
    st_id = g.get("sticker_file_id")

    try:
        gf = await http.post(f"{base}/getFile", json={"file_id": st_id})
        if gf.status_code == 200 and gf.json().get("ok", False):
            file_path = gf.json()["result"]["file_path"]
            # скачиваем bytes
            file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            got = await http.get(file_url)
            if got.status_code == 200 and got.content:
                files = {
                    "sticker": ("sticker.tgs", got.content, "application/x-tgsticker")
                }
                data = {"chat_id": str(chat), "disable_notification": "true"}
                await http.post(f"{base}/sendSticker", data=data, files=files)
    except Exception:
        logger.exception("Ошибка при отправке стикера", exc=True)

    text = (
        "Новый подарок\n"
        f"ID: {g.get('id')}\n"
        f"Цена: {g.get('price')}\n"
        f"Premium: {'да' if g.get('require_premium') else 'нет'}\n"
        f"Саплай: {g.get('total_amount') if g.get('is_limited') else '∞'}\n"
        f"Доступно: {g.get('available_amount') if g.get('is_limited') else '∞'}"
    )
    try:
        await http.post(
            f"{base}/sendMessage",
            json={"chat_id": chat, "text": text, "disable_notification": True},
        )
    except Exception:
        logger.exception("Ошибка при отправке текста", exc=True)

    await asyncio.sleep(0.04)



async def broadcast_new_gifts(gifts: List[Dict])->int:
    if not gifts: return 0
    targets=_collect_targets()
    if not targets: return 0
    sent=0
    async with httpx.AsyncClient(timeout=30) as http:
        for token, chats in targets:
            for chat in chats:
                for g in gifts:
                    try:
                        await _notify_one(http, token, chat, g)
                        sent+=1
                    except Exception:
                        logger.debug("notify._notify_one failed", exc_info=True)
                    await asyncio.sleep(0.12)
    return sent

def broadcast_new_gifts_sync(gifts: List[Dict])->int:
    try:
        loop=asyncio.get_running_loop()
        if loop.is_running():
            out={"n":0,"e":None}
            def runner():
                try: out["n"]=asyncio.run(broadcast_new_gifts(gifts))
                except Exception as e: out["e"]=e
            t=threading.Thread(target=runner, daemon=True); t.start(); t.join()
            if out["e"] is not None: raise out["e"]
            return int(out["n"])
    except RuntimeError:
        pass
    return asyncio.run(broadcast_new_gifts(gifts))
