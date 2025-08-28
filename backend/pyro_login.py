from datetime import datetime, timezone
import os, secrets, glob, threading, asyncio
from dataclasses import dataclass

from sqlalchemy.orm import Session
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, RPCError
from .models import ApiProfile, Account

SESS_ROOT = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESS_ROOT, exist_ok=True)


def _rpc(e: RPCError) -> dict:
    return {"error": "telegram_rpc", "error_code": e.__class__.__name__, "detail": str(e), "http": 400}


class _LoopThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result()

    def stop(self):
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._t.join(timeout=2)
        except Exception:
            pass


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

    def _sess(self, user_id: int, phone: str) -> str:
        d = os.path.join(SESS_ROOT, f"user_{user_id}")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{phone}.session")

    def _lid(self) -> str:
        return secrets.token_urlsafe(16)

    def _purge(self, session_path: str) -> None:
        for p in (session_path, session_path + "-journal", session_path + "-shm", session_path + "-wal"):
            try: os.remove(p)
            except FileNotFoundError: pass
            except Exception: pass
        try:
            base, _ = os.path.splitext(session_path)
            for p in glob.glob(base + "*.session*"):
                try: os.remove(p)
                except Exception: pass
        except Exception:
            pass

    def start_login(self, db: Session, user_id: int, api_profile_id: int, phone: str) -> dict:
        ap: ApiProfile = db.get(ApiProfile, api_profile_id)
        if not ap or ap.user_id != user_id:
            return {"error": "api_profile_not_found", "http": 400}

        sess = self._sess(user_id, phone)
        lt = _LoopThread()

        async def go():
            c = Client(sess, api_id=ap.api_id, api_hash=ap.api_hash)
            await c.connect()
            sent = await c.send_code(phone)
            return c, getattr(sent, "phone_code_hash", None)

        try:
            client, code_hash = lt.run(go())
        except RPCError as e:
            lt.stop(); self._purge(sess); return _rpc(e)
        except Exception as e:
            lt.stop(); self._purge(sess); return {"error": "unexpected", "detail": str(e), "http": 500}

        lid = self._lid()
        self._p[lid] = PendingLogin(
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
        return {"login_id": lid}

    def confirm_code(self, db: Session, login_id: str, code: str) -> dict:
        p = self._p.get(login_id)
        if not p:
            return {"error": "login_id_not_found", "http": 400}

        async def go():
            try:
                await p.client.sign_in(
                    phone_number=p.phone,
                    phone_code_hash=p.phone_code_hash or "",
                    phone_code=code
                )
            except SessionPasswordNeeded:
                return {"need_2fa": True}
            me = await p.client.get_me()
            stars = int(await p.client.get_stars_balance())
            return {"me": me, "stars": stars}

        try:
            r = p.loop.run(go())
            if r.get("need_2fa"):
                return r
            me, stars = r["me"], r["stars"]
        except RPCError as e:
            self._cleanup_pending(p, purge=True)
            return _rpc(e)
        except Exception as e:
            self._cleanup_pending(p, purge=True)
            return {"error": "unexpected", "detail": str(e), "http": 500}

        self._finalize(db, p, me, stars)
        self._cleanup_pending(p)
        del self._p[login_id]
        return {"ok": True}

    def confirm_password(self, db: Session, login_id: str, password: str) -> dict:
        p = self._p.get(login_id)
        if not p:
            return {"error": "login_id_not_found", "http": 400}

        async def go():
            await p.client.check_password(password)
            me = await p.client.get_me()
            stars = int(await p.client.get_stars_balance())
            return {"me": me, "stars": stars}

        try:
            r = p.loop.run(go())
            me, stars = r["me"], r["stars"]
        except RPCError as e:
            self._cleanup_pending(p, purge=True)
            return _rpc(e)
        except Exception as e:
            self._cleanup_pending(p, purge=True)
            return {"error": "unexpected", "detail": str(e), "http": 500}

        self._finalize(db, p, me, stars)
        self._cleanup_pending(p)
        del self._p[login_id]
        return {"ok": True}

    def cancel(self, login_id: str) -> dict:
        p = self._p.pop(login_id, None)
        if not p:
            return {"ok": True}
        self._cleanup_pending(p, purge=True)
        return {"ok": True}

    def _cleanup_pending(self, p: PendingLogin, purge: bool = False):
        try:
            p.loop.run(p.client.disconnect())
        except Exception:
            pass
        try:
            p.loop.stop()
        except Exception:
            pass
        if purge:
            try: self._purge(p.session_path)
            except Exception: pass

    def _finalize(self, db: Session, p: PendingLogin, me, stars: int) -> None:
        acc = db.query(Account).filter(Account.user_id == p.user_id, Account.phone == p.phone).first()
        if not acc:
            acc = Account(
                user_id=p.user_id,
                api_profile_id=p.api_profile_id,
                phone=p.phone,
                session_path=p.session_path
            )
            db.add(acc)
        acc.username = getattr(me, "username", None)
        acc.first_name = getattr(me, "first_name", None)
        acc.stars_amount = int(stars)
        acc.stars_nanos = 0
        acc.session_path = p.session_path
        acc.last_checked_at = datetime.now(timezone.utc)
        db.commit()
