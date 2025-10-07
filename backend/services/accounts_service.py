# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio
import glob
import os
import re
import threading
import time
from datetime import UTC, datetime, timedelta

from pyrogram.errors import AuthKeyUnregistered
from pyrogram.raw.functions.help import GetPremiumPromo
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..logger import logger
from ..models import Account
from .session_locks_service import session_lock_for
from .tg_clients_service import tg_call

STALE_MINUTES = 60


class _UserState:
    __slots__ = ("refreshing", "rev", "cv")

    def __init__(self):
        self.refreshing: bool = False
        self.rev: int = 0
        self.cv = threading.Condition()


_user_states: dict[int, _UserState] = {}
_user_states_guard = threading.Lock()


def _extract_premium_until_str(s: str) -> str | None:
    if not s:
        return None
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


def _purge_session_files(session_path: str) -> None:
    try:
        for p in (
            session_path,
            session_path + "-journal",
            session_path + "-shm",
            session_path + "-wal",
        ):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
        base, _ = os.path.splitext(session_path)
        for p in glob.glob(base + "*.session*"):
            try:
                os.remove(p)
            except Exception:
                pass
    except Exception:
        pass


def _delete_account_and_session(db: Session, acc: Account, *, reason: str | None = None) -> None:
    user_id = getattr(acc, "user_id", None)
    api_profile_id = getattr(acc, "api_profile_id", None)
    phone = getattr(acc, "phone", None)
    last_checked = getattr(acc, "last_checked_at", None)
    if last_checked and getattr(last_checked, "tzinfo", None) is None:
        last_checked = last_checked.replace(tzinfo=UTC)
    last_checked_str = last_checked.isoformat(timespec="seconds") if last_checked else None
    session_name = _sess_name(acc.session_path)
    reason_str = reason or "unspecified"
    warning_msg = (
        "accounts: deleting account "
        f"(acc_id={acc.id}, user_id={user_id}, phone={phone}, "
        f"session={session_name}, api_profile_id={api_profile_id}, "
        f"last_checked_at={last_checked_str}, reason={reason_str})"
    )
    logger.warning(warning_msg)
    _purge_session_files(acc.session_path)
    try:
        db.delete(acc)
        db.commit()
    except Exception:
        logger.exception(f"accounts: failed to delete account (acc_id={acc.id}, user_id={user_id})")
        db.rollback()


async def fetch_profile_and_stars(session_path: str, api_id: int, api_hash: str):
    me = await tg_call(session_path, api_id, api_hash, lambda c: c.get_me())
    stars = await tg_call(session_path, api_id, api_hash, lambda c: c.get_stars_balance())
    premium = bool(getattr(me, "is_premium", False))
    status_text = None
    if premium:
        try:
            promo = await tg_call(
                session_path, api_id, api_hash, lambda c: c.invoke(GetPremiumPromo())
            )
            status_text = getattr(promo, "status_text", None)
        except Exception:
            status_text = None
    until = _extract_premium_until_str(status_text or "") if premium else None
    return me, int(stars), premium, until


def _should_refresh(now: datetime, lc: datetime | None) -> bool:
    if lc and lc.tzinfo is None:
        lc = lc.replace(tzinfo=UTC)
    return lc is None or (now - lc) > timedelta(minutes=STALE_MINUTES)


def read_accounts(db: Session, user_id: int) -> list[dict]:
    rows = db.query(Account).filter(Account.user_id == user_id).order_by(Account.id.desc()).all()
    out = []
    for r in rows:
        dt = r.last_checked_at
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        out.append(
            {
                "id": r.id,
                "phone": r.phone,
                "username": r.username,
                "first_name": r.first_name,
                "is_premium": bool(r.is_premium),
                "premium_until": r.premium_until,
                "stars": float(r.stars_amount),
                "last_checked_at": dt.isoformat(timespec="seconds") if dt else None,
            }
        )
    return out


def any_stale(db: Session, user_id: int) -> bool:
    now = datetime.now(UTC)
    rows = db.query(Account.last_checked_at).filter(Account.user_id == user_id).all()
    for (lc,) in rows:
        if _should_refresh(now, lc):
            return True
    return False


def refresh_account(db: Session, acc: Account) -> Account | None:
    lk = session_lock_for(acc.session_path)
    t0 = time.perf_counter()
    api_profile_id = getattr(acc, "api_profile_id", None)
    api_profile = getattr(acc, "api_profile", None)
    api_id = getattr(api_profile, "api_id", None)
    user_id = getattr(acc, "user_id", None)
    phone = getattr(acc, "phone", None)
    session_name = _sess_name(acc.session_path)
    start_msg = (
        "accounts.refresh: start "
        f"(acc_id={acc.id}, user_id={user_id}, phone={phone}, "
        f"session={session_name}, api_profile_id={api_profile_id}, api_id={api_id})"
    )
    logger.info(start_msg)
    with lk:

        async def work():
            fetch_begin_msg = (
                "accounts.refresh: fetch begin "
                f"(acc_id={acc.id}, user_id={user_id}, "
                f"session_path={acc.session_path}, api_id={api_id})"
            )
            logger.debug(fetch_begin_msg)
            me, stars, premium, until = await fetch_profile_and_stars(
                acc.session_path, acc.api_profile.api_id, acc.api_profile.api_hash
            )
            fetch_done_msg = (
                "accounts.refresh: fetch done "
                f"(acc_id={acc.id}, user_id={user_id}, tg_id={getattr(me, 'id', None)}, "
                f"username={getattr(me, 'username', None)}, stars={stars}, "
                f"premium={premium}, premium_until={until})"
            )
            logger.debug(fetch_done_msg)
            prev_first = acc.first_name
            prev_username = acc.username
            prev_premium = acc.is_premium
            prev_until = acc.premium_until
            prev_stars = acc.stars_amount
            prev_checked = acc.last_checked_at
            if prev_checked and getattr(prev_checked, "tzinfo", None) is None:
                prev_checked = prev_checked.replace(tzinfo=UTC)
            prev_checked_iso = prev_checked.isoformat(timespec="seconds") if prev_checked else None
            acc.first_name = getattr(me, "first_name", None)
            acc.username = getattr(me, "username", None)
            acc.is_premium = premium
            acc.premium_until = until
            acc.stars_amount = int(stars)
            acc.last_checked_at = datetime.now(UTC)
            new_checked_iso = acc.last_checked_at.isoformat(timespec="seconds")
            apply_msg = (
                "accounts.refresh: applying updates "
                f"(acc_id={acc.id}, user_id={user_id}, "
                f"first_name={prev_first!r}->{acc.first_name!r}, "
                f"username={prev_username!r}->{acc.username!r}, "
                f"stars={prev_stars}->{acc.stars_amount}, "
                f"premium={prev_premium}->{acc.is_premium}, "
                f"premium_until={prev_until}->{acc.premium_until}, "
                f"last_checked_at={prev_checked_iso}->{new_checked_iso})"
            )
            logger.debug(apply_msg)
            db.commit()
            commit_msg = (
                "accounts.refresh: commit succeeded "
                f"(acc_id={acc.id}, user_id={user_id}, last_checked_at={new_checked_iso})"
            )
            logger.debug(commit_msg)
            return acc

        try:
            logger.debug(
                f"accounts.refresh: entering asyncio run (acc_id={acc.id}, user_id={user_id})"
            )
            res: Account = asyncio.run(work())
            dt = (time.perf_counter() - t0) * 1000
            done_msg = (
                "accounts.refresh: done "
                f"(acc_id={acc.id}, user_id={user_id}, stars={res.stars_amount}, dt_ms={dt:.0f})"
            )
            logger.info(done_msg)
            return res
        except AuthKeyUnregistered:
            auth_warning_msg = (
                "accounts.refresh: AUTH_KEY_UNREGISTERED -> remove "
                f"(acc_id={acc.id}, user_id={user_id}, session={session_name})"
            )
            logger.warning(auth_warning_msg)
            _delete_account_and_session(db, acc, reason="AUTH_KEY_UNREGISTERED(refresh)")
            return None
        except Exception:
            refresh_error_msg = (
                "accounts.refresh: failed "
                f"(acc_id={acc.id}, user_id={user_id}, session={session_name})"
            )
            logger.exception(refresh_error_msg)
            raise


def _refresh_user_accounts_worker(user_id: int):
    st = _user_state(user_id)
    with st.cv:
        if st.refreshing:
            logger.debug(f"accounts.bg_refresh: already refreshing (user_id={user_id})")
            return
        st.refreshing = True
    db2 = SessionLocal()
    try:
        now = datetime.now(UTC)
        rows = (
            db2.query(Account).filter(Account.user_id == user_id).order_by(Account.id.desc()).all()
        )
        for r in rows:
            try:
                if _should_refresh(now, r.last_checked_at):
                    refresh_account(db2, r)
            except Exception:
                logger.exception(f"accounts.bg_refresh: failed (acc_id={r.id})")
    finally:
        try:
            db2.close()
        except Exception:
            logger.exception(f"accounts.bg_refresh: failed to close session (user_id={user_id})")
        finally:
            with st.cv:
                st.refreshing = False
                st.rev += 1
                st.cv.notify_all()


def schedule_user_refresh(user_id: int) -> None:
    threading.Thread(target=_refresh_user_accounts_worker, args=(user_id,), daemon=True).start()


def iter_refresh_steps_core(db: Session, *, acc: Account, api_id: int, api_hash: str):
    lk = session_lock_for(acc.session_path)
    api_profile_id = getattr(acc, "api_profile_id", None)
    api_profile = getattr(acc, "api_profile", None)
    api_profile_api_id = getattr(api_profile, "api_id", None)
    user_id = getattr(acc, "user_id", None)
    phone = getattr(acc, "phone", None)
    session_name = _sess_name(acc.session_path)
    stream_start_msg = (
        "accounts.stream: start "
        f"(acc_id={acc.id}, user_id={user_id}, phone={phone}, "
        f"session={session_name}, api_profile_id={api_profile_id}, "
        f"api_id={api_id}, api_profile_api_id={api_profile_api_id})"
    )
    logger.info(stream_start_msg)
    with lk:
        yield {"stage": "connect", "message": "Соединяюсь…"}
        time.sleep(0.5)
        try:
            stream_fetch_begin_msg = (
                "accounts.stream: fetch begin "
                f"(acc_id={acc.id}, user_id={user_id}, "
                f"session_path={acc.session_path}, api_id={api_id})"
            )
            logger.debug(stream_fetch_begin_msg)
            me, stars, premium, until = asyncio.run(
                fetch_profile_and_stars(acc.session_path, api_id, api_hash)
            )
            stream_fetch_done_msg = (
                "accounts.stream: fetch done "
                f"(acc_id={acc.id}, user_id={user_id}, tg_id={getattr(me, 'id', None)}, "
                f"username={getattr(me, 'username', None)}, stars={stars}, "
                f"premium={premium}, premium_until={until})"
            )
            logger.debug(stream_fetch_done_msg)
        except AuthKeyUnregistered:
            stream_auth_warning_msg = (
                "accounts.stream: AUTH_KEY_UNREGISTERED -> removing account "
                f"(acc_id={acc.id}, user_id={user_id}, session={session_name})"
            )
            logger.warning(stream_auth_warning_msg)
            _delete_account_and_session(db, acc, reason="AUTH_KEY_UNREGISTERED(stream)")
            yield {
                "error": "session_invalid",
                "error_code": "AUTH_KEY_UNREGISTERED",
                "detail": "Сессия невалидна. Авторизуйтесь заново.",
            }
            return
        except Exception as e:
            stream_error_msg = (
                "accounts.stream: unexpected error "
                f"(acc_id={acc.id}, user_id={user_id}, session={session_name})"
            )
            logger.exception(stream_error_msg)
            yield {"error": "internal_error", "detail": str(e)}
            return

        yield {"stage": "profile", "message": "Проверяю профиль…"}
        time.sleep(0.5)
        yield {"stage": "stars", "message": "Проверяю звёзды…"}
        time.sleep(0.5)
        yield {"stage": "premium", "message": "Проверяю премиум…"}
        time.sleep(0.5)

        prev_first = acc.first_name
        prev_username = acc.username
        prev_premium = acc.is_premium
        prev_until = acc.premium_until
        prev_stars = acc.stars_amount
        prev_checked = acc.last_checked_at
        if prev_checked and getattr(prev_checked, "tzinfo", None) is None:
            prev_checked = prev_checked.replace(tzinfo=UTC)
        prev_checked_iso = prev_checked.isoformat(timespec="seconds") if prev_checked else None

        acc.first_name = getattr(me, "first_name", None)
        acc.username = getattr(me, "username", None)
        acc.is_premium = premium
        acc.premium_until = until
        acc.stars_amount = int(stars)
        acc.last_checked_at = datetime.now(UTC)
        new_checked_iso = acc.last_checked_at.isoformat(timespec="seconds")

        stream_apply_msg = (
            "accounts.stream: applying updates "
            f"(acc_id={acc.id}, user_id={user_id}, "
            f"first_name={prev_first!r}->{acc.first_name!r}, "
            f"username={prev_username!r}->{acc.username!r}, "
            f"stars={prev_stars}->{acc.stars_amount}, "
            f"premium={prev_premium}->{acc.is_premium}, "
            f"premium_until={prev_until}->{acc.premium_until}, "
            f"last_checked_at={prev_checked_iso}->{new_checked_iso})"
        )
        logger.debug(stream_apply_msg)

        db.commit()
        stream_commit_msg = (
            "accounts.stream: commit succeeded "
            f"(acc_id={acc.id}, user_id={user_id}, last_checked_at={new_checked_iso})"
        )
        logger.debug(stream_commit_msg)

        yield {"stage": "save", "message": "Сохраняю…"}
        time.sleep(0.5)

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
            },
        }
        stream_done_msg = (
            "accounts.stream: done "
            f"(acc_id={acc.id}, user_id={user_id}, session={session_name}, "
            f"stars={acc.stars_amount}, premium={acc.is_premium}, "
            f"premium_until={acc.premium_until})"
        )
        logger.info(stream_done_msg)
