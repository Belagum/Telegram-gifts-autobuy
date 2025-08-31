# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

from typing import Optional, Dict
from sqlalchemy.orm import Session

from .channels_service import norm_ch_id
from ..db import SessionLocal
from ..models import UserSettings

def read_user_settings(user_id: int) -> Dict[str, Optional[str | int]]:
    db: Session = SessionLocal()
    try:
        s = db.get(UserSettings, user_id)
        return {
            "bot_token": s.bot_token if s else None,
            "notify_chat_id": s.notify_chat_id if s else None,
        }
    finally:
        db.close()

def set_user_settings(user_id: int, bot_token: Optional[str], notify_chat_id: Optional[str | int]) -> Dict[str, Optional[str | int]]:
    db: Session = SessionLocal()
    try:
        s = db.get(UserSettings, user_id)
        if not s:
            s = UserSettings(user_id=user_id)
            db.add(s)

        token_norm = (bot_token or "").strip() or None

        if notify_chat_id is None or str(notify_chat_id).strip() == "":
            chat_norm = None
        else:
            chat_norm = norm_ch_id(notify_chat_id)

        s.bot_token = token_norm
        s.notify_chat_id = chat_norm
        db.commit()
        return {"bot_token": s.bot_token, "notify_chat_id": s.notify_chat_id}
    finally:
        db.close()

