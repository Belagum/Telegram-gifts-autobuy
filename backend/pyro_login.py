# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import asyncio
import glob
import os
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from pyrogram import Client
from pyrogram.errors import RPCError, SessionPasswordNeeded
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.infrastructure.db.models import Account, ApiProfile
from backend.services.accounts_service import fetch_profile_and_stars
from backend.shared.logging import logger

SESS_ROOT = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESS_ROOT, exist_ok=True)


def _rpc(e: RPCError) -> dict:
    logger.warning(f"pyro_login: RPC error type={e.__class__.__name__} detail={str(e)[:200]}")
    return {
        "error": "telegram_rpc",
        "error_code": e.__class__.__name__,
        "detail": str(e),
        "http": 400,
    }


class _LoopThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._t = threading.Thread(target=self._run, daemon=True)
        logger.debug(f"pyro_login: creating loop thread name={self._t.name}")
        self._t.start()
        logger.debug(f"pyro_login: loop thread started name={self._t.name}")

    def _run(self):
        asyncio.set_event_loop(self.loop)
        logger.debug(f"pyro_login: loop runner start thread={threading.current_thread().name}")
        try:
            self.loop.run_forever()
        finally:
            logger.debug(f"pyro_login: loop runner stop thread={threading.current_thread().name}")

    def run(self, coro):
        logger.debug(f"pyro_login: scheduling coroutine on loop thread={self._t.name}")
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result()

    def stop(self):
        logger.debug(f"pyro_login: stopping loop thread={self._t.name}")
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._t.join(timeout=2)
        except Exception:
            logger.exception(f"pyro_login: loop thread stop failed name={self._t.name}")
        else:
            logger.debug(f"pyro_login: loop thread stopped name={self._t.name}")


@dataclass
class PendingLogin:
    user_id: int
    api_profile_id: int
    phone: str
    session_path: str
    api_id: int
    api_hash: str
    loop: _LoopThread
    client: Client
    phone_code_hash: str | None = None


class PyroLoginManager:
    def __init__(self) -> None:
        self._p: dict[str, PendingLogin] = {}
        logger.debug("pyro_login: manager initialized")

    def _sess(self, user_id: int, phone: str) -> str:
        d = os.path.join(SESS_ROOT, f"user_{user_id}")
        os.makedirs(d, exist_ok=True)
        sess_path = os.path.join(d, f"{phone}.session")
        logger.debug(
            f"pyro_login: session path prepared user_id={user_id} phone={phone} path={sess_path}"
        )
        return sess_path

    def _lid(self) -> str:
        lid = secrets.token_urlsafe(16)
        logger.debug(f"pyro_login: generated login_id={lid}")
        return lid

    def _purge(self, session_path: str) -> None:
        logger.info(f"pyro_login: purging session files path={session_path}")
        for p in (
            session_path,
            session_path + "-journal",
            session_path + "-shm",
            session_path + "-wal",
        ):
            try:
                os.remove(p)
                logger.debug(f"pyro_login: removed session file path={p}")
            except FileNotFoundError:
                logger.debug(f"pyro_login: session file not found path={p}")
            except Exception:
                logger.exception(f"pyro_login: failed to remove session file path={p}")
        try:
            base, _ = os.path.splitext(session_path)
            for p in glob.glob(base + "*.session*"):
                try:
                    os.remove(p)
                    logger.debug(f"pyro_login: removed extra session file path={p}")
                except Exception:
                    logger.exception(f"pyro_login: failed to remove extra session file path={p}")
        except Exception:
            logger.exception(
                f"pyro_login: glob purge failed base={os.path.splitext(session_path)[0]}"
            )

    def start_login(self, db: Session, user_id: int, api_profile_id: int, phone: str) -> dict:
        logger.info(
            f"pyro_login: start_login user_id={user_id} "
            f"api_profile_id={api_profile_id} phone={phone}"
        )
        ap = db.get(ApiProfile, api_profile_id)
        if not ap or ap.user_id != user_id:
            logger.warning(
                f"pyro_login: api profile mismatch user_id={user_id} "
                f"api_profile_id={api_profile_id}"
            )
            return {"error": "api_profile_not_found", "http": 400}

        logger.debug(
            f"pyro_login: resolved api profile api_id={ap.api_id} hash={'***'} user_id={user_id}"
        )

        sess = self._sess(user_id, phone)
        lt = _LoopThread()

        async def go():
            logger.debug(f"pyro_login: connecting session={sess} phone={phone}")
            c = Client(sess, api_id=ap.api_id, api_hash=ap.api_hash)
            await c.connect()
            logger.debug(f"pyro_login: connected session={sess}")
            sent = await c.send_code(phone)
            logger.info(
                f"pyro_login: code sent session={sess} phone={phone} "
                f"hash={getattr(sent, 'phone_code_hash', None)}"
            )
            return c, getattr(sent, "phone_code_hash", None)

        try:
            client, code_hash = lt.run(go())
        except RPCError as e:
            logger.warning(
                f"pyro_login: start_login RPC error user_id={user_id} phone={phone} detail={e}"
            )
            lt.stop()
            self._purge(sess)
            return _rpc(e)
        except Exception as e:
            logger.exception(
                f"pyro_login: start_login unexpected error user_id={user_id} phone={phone}"
            )
            lt.stop()
            self._purge(sess)
            return {"error": "unexpected", "detail": str(e), "http": 500}

        lid = self._lid()
        pending = PendingLogin(
            user_id=user_id,
            api_profile_id=api_profile_id,
            phone=phone,
            session_path=sess,
            api_id=ap.api_id,
            api_hash=ap.api_hash,
            loop=lt,
            client=client,
            phone_code_hash=code_hash,
        )
        self._p[lid] = pending
        logger.info(
            f"pyro_login: pending login created login_id={lid} user_id={user_id} phone={phone}"
        )
        return {"login_id": lid}

    def complete_login(self, db: Session, login_id: str, code: str) -> dict:
        logger.info(f"pyro_login: complete_login login_id={login_id} code_len={len(code or '')}")
        p = self._p.get(login_id)
        if not p:
            logger.warning(f"pyro_login: login_id not found login_id={login_id}")
            return {"error": "login_id_not_found", "http": 400}

        async def go():
            logger.debug(f"pyro_login: sign_in attempt login_id={login_id} phone={p.phone}")
            try:
                await p.client.sign_in(
                    phone_number=p.phone, phone_code_hash=p.phone_code_hash or "", phone_code=code
                )
            except SessionPasswordNeeded:
                logger.info(f"pyro_login: 2fa required login_id={login_id} phone={p.phone}")
                return {"need_2fa": True}
            logger.debug(f"pyro_login: sign_in ok login_id={login_id}")
            return await fetch_profile_and_stars(p.session_path, p.api_id, p.api_hash)

        try:
            r = p.loop.run(go())
            if isinstance(r, dict) and r.get("need_2fa"):
                return r
            me, stars, premium, until = r
        except RPCError as e:
            logger.warning(f"pyro_login: complete_login RPC error login_id={login_id} detail={e}")
            self._cleanup_pending(p, purge=True)
            return _rpc(e)
        except Exception as e:
            logger.exception(f"pyro_login: complete_login unexpected error login_id={login_id}")
            self._cleanup_pending(p, purge=True)
            return {"error": "unexpected", "detail": str(e), "http": 500}

        self._finalize(db, p, me, stars, premium, until)
        self._cleanup_pending(p)
        del self._p[login_id]
        logger.info(f"pyro_login: complete_login success login_id={login_id}")
        return {"ok": True}

    def confirm_code(self, db: Session, login_id: str, code: str) -> dict:
        logger.debug(f"pyro_login: confirm_code alias login_id={login_id}")
        return self.complete_login(db, login_id, code)

    def confirm_password(self, db: Session, login_id: str, password: str) -> dict:
        logger.info(
            f"pyro_login: confirm_password login_id={login_id} password_len={len(password or '')}"
        )
        p = self._p.get(login_id)
        if not p:
            logger.warning(f"pyro_login: login_id not found for password login_id={login_id}")
            return {"error": "login_id_not_found", "http": 400}

        async def go():
            logger.debug(f"pyro_login: check_password login_id={login_id}")
            await p.client.check_password(password)
            return await fetch_profile_and_stars(p.session_path, p.api_id, p.api_hash)

        try:
            me, stars, premium, until = p.loop.run(go())
        except RPCError as e:
            logger.warning(f"pyro_login: confirm_password RPC error login_id={login_id} detail={e}")
            self._cleanup_pending(p, purge=True)
            return _rpc(e)
        except Exception as e:
            logger.exception(f"pyro_login: confirm_password unexpected error login_id={login_id}")
            self._cleanup_pending(p, purge=True)
            return {"error": "unexpected", "detail": str(e), "http": 500}

        self._finalize(db, p, me, stars, premium, until)
        self._cleanup_pending(p)
        del self._p[login_id]
        logger.info(f"pyro_login: confirm_password success login_id={login_id}")
        return {"ok": True}

    def cancel(self, login_id: str) -> dict:
        logger.info(f"pyro_login: cancel login_id={login_id}")
        p = self._p.pop(login_id, None)
        if not p:
            logger.debug(f"pyro_login: cancel no pending login login_id={login_id}")
            return {"ok": True}
        self._cleanup_pending(p, purge=True)
        logger.info(f"pyro_login: cancel done login_id={login_id}")
        return {"ok": True}

    def _cleanup_pending(self, p: PendingLogin, purge: bool = False):
        logger.debug(
            f"pyro_login: cleanup pending user_id={p.user_id} phone={p.phone} purge={purge}"
        )
        try:
            p.loop.run(p.client.disconnect())
            logger.debug(f"pyro_login: client disconnected user_id={p.user_id} phone={p.phone}")
        except Exception:
            logger.exception(
                f"pyro_login: client disconnect failed user_id={p.user_id} phone={p.phone}"
            )
        try:
            p.loop.stop()
        except Exception:
            logger.exception(f"pyro_login: loop stop failed user_id={p.user_id} phone={p.phone}")
        if purge:
            try:
                self._purge(p.session_path)
            except Exception:
                logger.exception(f"pyro_login: purge failed user_id={p.user_id} phone={p.phone}")

    def _finalize(
        self, db: Session, p: PendingLogin, me, stars: int, premium: bool, until: str | None
    ) -> None:
        tg_id = int(getattr(me, "id", 0)) or None
        logger.info(
            f"pyro_login: finalize user_id={p.user_id} phone={p.phone} tg_id={tg_id} stars={stars}"
        )
        acc = (
            db.query(Account).filter(Account.user_id == p.user_id, Account.phone == p.phone).first()
        )
        if not acc and tg_id:
            acc = db.get(Account, tg_id)
            if not acc:
                logger.debug(f"pyro_login: creating new account tg_id={tg_id} user_id={p.user_id}")
                acc = Account(
                    id=tg_id,
                    user_id=p.user_id,
                    api_profile_id=p.api_profile_id,
                    phone=p.phone,
                    session_path=p.session_path,
                )
                db.add(acc)
            else:
                logger.debug(f"pyro_login: reusing account tg_id={tg_id} user_id={p.user_id}")
                acc.user_id = p.user_id
                acc.api_profile_id = p.api_profile_id
                acc.phone = p.phone
                acc.session_path = p.session_path
        if not acc:
            logger.debug(
                f"pyro_login: creating account without tg_id user_id={p.user_id} phone={p.phone}"
            )
            acc = Account(
                user_id=p.user_id,
                api_profile_id=p.api_profile_id,
                phone=p.phone,
                session_path=p.session_path,
            )
            db.add(acc)

        acc.username = getattr(me, "username", None)
        acc.first_name = getattr(me, "first_name", None)
        acc.stars_amount = int(stars)
        acc.is_premium = bool(premium)
        acc.premium_until = until
        acc.session_path = p.session_path
        acc.last_checked_at = datetime.now(UTC)

        try:
            db.commit()
            logger.info(
                f"pyro_login: account updated user_id={p.user_id} phone={p.phone} tg_id={tg_id}"
            )
        except IntegrityError:
            logger.warning(
                f"pyro_login: commit integrity error user_id={p.user_id} phone={p.phone}"
            )
            db.rollback()
            if tg_id:
                acc = db.get(Account, tg_id)
                if acc:
                    logger.debug(
                        f"pyro_login: retry update existing account tg_id={tg_id} "
                        f"user_id={p.user_id}"
                    )
                    acc.user_id = p.user_id
                    acc.api_profile_id = p.api_profile_id
                    acc.phone = p.phone
                    acc.session_path = p.session_path
                    acc.username = getattr(me, "username", None)
                    acc.first_name = getattr(me, "first_name", None)
                    acc.stars_amount = int(stars)
                    acc.is_premium = bool(premium)
                    acc.premium_until = until
                    acc.last_checked_at = datetime.now(UTC)
                    db.commit()
                    logger.info(
                        f"pyro_login: account updated after retry tg_id={tg_id} user_id={p.user_id}"
                    )
            else:
                raise
