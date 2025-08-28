from typing import Optional, Dict

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import UserSettings

def read_user_settings(user_id: int) -> Dict[str, Optional[str]]:
    db: Session = SessionLocal()
    try:
        s = db.get(UserSettings, user_id)
        return {"bot_token": s.bot_token if s else None}
    finally:
        db.close()

def set_user_settings(user_id: int, bot_token: Optional[str]) -> Dict[str, Optional[str]]:
    db: Session = SessionLocal()
    try:
        s = db.get(UserSettings, user_id)
        if not s:
            s = UserSettings(user_id=user_id, bot_token=bot_token or None)
            db.add(s)
        else:
            s.bot_token = bot_token or None
        db.commit()
        return {"bot_token": s.bot_token}
    finally:
        db.close()
