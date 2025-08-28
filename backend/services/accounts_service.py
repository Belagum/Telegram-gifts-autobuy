import asyncio, time, os, threading, glob
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy.orm import Session
from pyrogram import Client
from pyrogram.errors import AuthKeyUnregistered
from pyrogram.raw.functions.help import GetPremiumPromo

from ..models import Account
from ..logger import logger
from ..db import SessionLocal

STALE_MINUTES = 60

_session_locks: dict[str, threading.RLock] = {}
_session_locks_guard = threading.Lock()

class _UserState:
    __slots__ = ("refreshing", "rev", "cv")
    def __init__(self):
        self.refreshing: bool = False
        self.rev: int = 0
        self.cv = threading.Condition()

_user_states: dict[int, _UserState] = {}
_user_states_guard = threading.Lock()

def _extract_premium_until_str(s: str) -> str | None:
    if not s: return None
    s = s.replace("\xa0", " ")
    m = re.search(r"(\d{2}[./]\d{2}[./]\d{4})", s)
    return m.group(1) if m else None

def _user_state(uid: int) -> _UserState:
    with _user_states_guard:
        st = _user_states.get(uid)
        if not st:
            st = _UserState()
            _user_states[uid] = st
        return st

def begin_user_refresh(user_id: int) -> None:
    st = _user_state(user_id)
    with st.cv:
        st.refreshing = True

def end_user_refresh(user_id: int) -> None:
    st = _user_state(user_id)
    with st.cv:
        st.refreshing = False
        st.rev += 1
        st.cv.notify_all()

def wait_until_ready(user_id: int, timeout_sec: float) -> bool:
    st = _user_state(user_id)
    end = time.monotonic() + timeout_sec
    with st.cv:
        while st.refreshing:
            rem = end - time.monotonic()
            if rem <= 0:
                return False
            st.cv.wait(rem)
    return True

def _sess_name(path: str) -> str:
    return os.path.basename(path or "") or "unknown.session"

def _lock_for(session_path: str) -> threading.RLock:
    with _session_locks_guard:
        lk = _session_locks.get(session_path)
        if lk is None:
            lk = threading.RLock()
            _session_locks[session_path] = lk
            logger.debug(f"accounts: created lock for session {_sess_name(session_path)}")
        return lk

def _purge_session_files(session_path: str) -> None:
    try:
        for p in (session_path, session_path + "-journal", session_path + "-shm", session_path + "-wal"):
            try: os.remove(p)
            except FileNotFoundError: pass
        base, _ = os.path.splitext(session_path)
        for p in glob.glob(base + "*.session*"):
            try: os.remove(p)
            except Exception: pass
    except Exception:
        pass

def _delete_account_and_session(db: Session, acc: Account) -> None:
    logger.warning(
        f"accounts: deleting invalid session & account (acc_id={acc.id}, session={_sess_name(acc.session_path)})"
    )
    _purge_session_files(acc.session_path)
    try:
        db.delete(acc); db.commit()
    except Exception:
        logger.exception(f"accounts: failed to delete account (acc_id={acc.id})")
        db.rollback()


async def _fetch_profile_and_stars(session_path: str, api_id: int, api_hash: str):
    logger.debug(f"accounts: connecting (session={_sess_name(session_path)})")
    async with Client(session_path, api_id=api_id, api_hash=api_hash) as c:
        me = await c.get_me()
        stars = await c.get_stars_balance()
        premium = bool(getattr(me, "is_premium", False))
        status_text = None
        if premium:
            try:
                promo = await c.invoke(GetPremiumPromo())
                status_text = getattr(promo, "status_text", None)
            except Exception:
                status_text = None
        until = _extract_premium_until_str(status_text or "") if premium else None
        logger.debug(
            f"accounts: fetched profile & stars (session={_sess_name(session_path)}, stars={int(stars)}, premium={premium}, until={until})"
        )
        return me, int(stars), premium, until


def _should_refresh(now: datetime, lc: datetime | None) -> bool:
    if lc and lc.tzinfo is None:
        lc = lc.replace(tzinfo=timezone.utc)
    return lc is None or (now - lc) > timedelta(minutes=STALE_MINUTES)

def read_accounts(db:Session, user_id:int)->list[dict]:
    rows=db.query(Account).filter(Account.user_id==user_id).order_by(Account.id.desc()).all()
    out=[]
    for r in rows:
        dt=r.last_checked_at
        if dt and dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        out.append({
            "id":r.id,
            "phone":r.phone,
            "username":r.username,
            "first_name":r.first_name,
            "is_premium": bool(r.is_premium),
            "premium_until": r.premium_until,
            "stars": float(r.stars_amount),
            "last_checked_at":dt.isoformat(timespec="seconds") if dt else None
        })
    return out



def any_stale(db:Session, user_id:int)->bool:
    now=datetime.now(timezone.utc)
    rows=db.query(Account.last_checked_at).filter(Account.user_id==user_id).all()
    for (lc,) in rows:
        if _should_refresh(now, lc): return True
    return False

# services/accounts_service.py — запись в БД и отдельный стейт в стриме; убран stars_nanos
def refresh_account(db: Session, acc: Account) -> Account | None:
    lk = _lock_for(acc.session_path); t0 = time.perf_counter()
    logger.info(f"accounts.refresh: start (acc_id={acc.id}, session={_sess_name(acc.session_path)})")
    with lk:
        async def work():
            me, stars, premium, until = await _fetch_profile_and_stars(
                acc.session_path, acc.api_profile.api_id, acc.api_profile.api_hash
            )
            acc.first_name = getattr(me, "first_name", None)
            acc.username = getattr(me, "username", None)
            acc.is_premium = premium
            acc.premium_until = until
            acc.stars_amount = int(stars)
            acc.last_checked_at = datetime.now(timezone.utc)
            db.commit()
            return acc
        try:
            res = asyncio.run(work()); dt = (time.perf_counter() - t0) * 1000
            logger.info(f"accounts.refresh: done (acc_id={acc.id}, stars={res.stars_amount}, dt_ms={dt:.0f})")
            return res
        except AuthKeyUnregistered:
            logger.warning(
                f"accounts.refresh: AUTH_KEY_UNREGISTERED -> remove (acc_id={acc.id}, session={_sess_name(acc.session_path)})"
            )
            _delete_account_and_session(db, acc)
            return None
        except Exception:
            logger.exception(
                f"accounts.refresh: failed (acc_id={acc.id}, session={_sess_name(acc.session_path)})"
            )
            raise



def _refresh_user_accounts_worker(user_id: int):
    st = _user_state(user_id)
    with st.cv:
        if st.refreshing:
            return
        st.refreshing = True
    db2 = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = db2.query(Account).filter(Account.user_id == user_id).order_by(Account.id.desc()).all()
        for r in rows:
            try:
                if _should_refresh(now, r.last_checked_at):
                    refresh_account(db2, r)
            except Exception:
                logger.exception(f"accounts.bg_refresh: failed (acc_id={r.id})")
    finally:
        db2.close()
        with st.cv:
            st.refreshing = False
            st.rev += 1
            st.cv.notify_all()

def schedule_user_refresh(user_id:int)->None:
    threading.Thread(target=_refresh_user_accounts_worker, args=(user_id,), daemon=True).start()

def iter_refresh_steps_core(db: Session, *, acc: Account, api_id: int, api_hash: str):
    lk = _lock_for(acc.session_path)
    logger.info(f"accounts.stream: start (acc_id={acc.id}, session={_sess_name(acc.session_path)})")
    with lk:
        yield {"stage": "connect", "message": "Соединяюсь…"}; time.sleep(0.5)
        try:
            me, stars, premium, until = asyncio.run(_fetch_profile_and_stars(acc.session_path, api_id, api_hash))
        except AuthKeyUnregistered:
            _delete_account_and_session(db, acc)
            yield {"error":"session_invalid","error_code":"AUTH_KEY_UNREGISTERED","detail":"Сессия невалидна. Авторизуйтесь заново."}
            logger.warning(f"accounts.stream: AUTH_KEY_UNREGISTERED -> removed (acc_id={acc.id})")
            return
        except Exception as e:
            logger.exception(f"accounts.stream: unexpected error (acc_id={acc.id})")
            yield {"error":"internal_error","detail":str(e)}
            return

        yield {"stage":"profile","message":"Проверяю профиль…"}; time.sleep(0.5)
        yield {"stage":"stars","message":"Проверяю звёзды…"}; time.sleep(0.5)
        yield {"stage":"premium","message":"Проверяю премиум…"}; time.sleep(0.5)

        acc.first_name = getattr(me, "first_name", None)
        acc.username = getattr(me, "username", None)
        acc.is_premium = premium
        acc.premium_until = until
        acc.stars_amount = int(stars)
        acc.last_checked_at = datetime.now(timezone.utc)
        db.commit()

        logger.debug(f"accounts.stream: saved (acc_id={acc.id}, stars={acc.stars_amount}, premium={acc.is_premium}, until={acc.premium_until})")
        yield {"stage":"save","message":"Сохраняю…"}; time.sleep(0.5)

        yield {
            "done": True,
            "message": "Готово",
            "account": {
                "id": acc.id,
                "phone": acc.phone,
                "username": acc.username,
                "first_name": acc.first_name,
                "is_premium": bool(acc.is_premium),
                "premium_until": acc.premium_until,
                "stars": float(acc.stars_amount),
                "last_checked_at": acc.last_checked_at.isoformat(timespec="seconds"),
            }
        }
        logger.info(f"accounts.stream: done (acc_id={acc.id}, session={_sess_name(acc.session_path)})")
