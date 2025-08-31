# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import re
from typing import Optional, Dict
from sqlalchemy.orm import Session
from .channels_service import norm_ch_id
from ..db import SessionLocal
from ..models import UserSettings

def _norm_peer_id(v) -> int:
    s = str(v or "").strip()
    if not s: raise ValueError("invalid id")
    neg = s.startswith("-")
    digits = re.sub(r"\D", "", s[1:] if neg else s)
    if not digits: raise ValueError("invalid id")
    n = int(digits)
    return -n if neg else n

def read_user_settings(user_id: int) -> Dict[str, Optional[str | int | bool]]:
    db: Session = SessionLocal()
    try:
        s = db.get(UserSettings, user_id)
        return {
            "bot_token": s.bot_token if s else None,
            "notify_chat_id": s.notify_chat_id if s else None,
            "buy_target_id": s.buy_target_id if s else None,
        }
    finally:
        db.close()

def set_user_settings(user_id: int, bot_token: Optional[str], notify_chat_id: Optional[str | int], buy_target_id: Optional[str | int]) -> Dict[str, Optional[str | int | bool]]:
    db: Session = SessionLocal()
    try:
        s = db.get(UserSettings, user_id)
        if not s:
            s = UserSettings(user_id=user_id); db.add(s)

        s.bot_token = ((bot_token or "").strip() or None)

        if notify_chat_id is None or str(notify_chat_id).strip()=="":
            s.notify_chat_id = None
        else:
            s.notify_chat_id = norm_ch_id(notify_chat_id)

        if buy_target_id is None or str(buy_target_id).strip()=="":
            s.buy_target_id = None
        else:
            s.buy_target_id = _norm_peer_id(buy_target_id)

        db.commit()
        return {"bot_token": s.bot_token, "notify_chat_id": s.notify_chat_id, "buy_target_id": s.buy_target_id}
    finally:
        db.close()