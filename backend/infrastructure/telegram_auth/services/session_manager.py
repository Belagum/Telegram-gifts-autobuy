# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import secrets
import threading
import time

from backend.infrastructure.telegram_auth.exceptions import LoginNotFoundError
from backend.infrastructure.telegram_auth.models.dto import LoginSession
from backend.shared.logging import logger

# Сколько живёт незавершённый логин. Брошенный (модалку закрыли, код не ввели)
# логин иначе висел бы в памяти вечно и держал подключённый Pyrogram-клиент.
_LOGIN_TTL_SECONDS = 600


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, LoginSession] = {}
        self._created_at: dict[str, float] = {}
        self._lock = threading.Lock()
        logger.debug("SessionManager: initialized")

    def _evict_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            stale = [
                lid
                for lid, ts in self._created_at.items()
                if now - ts > _LOGIN_TTL_SECONDS
            ]
            evicted = []
            for lid in stale:
                session = self._sessions.pop(lid, None)
                self._created_at.pop(lid, None)
                if session is not None:
                    evicted.append((lid, session))
        # отключаем клиентов вне лока — disconnect может быть небыстрым
        for lid, session in evicted:
            self._safe_disconnect(session)
            logger.info(f"SessionManager: evicted stale login_id={lid}")

    @staticmethod
    def _safe_disconnect(session: LoginSession) -> None:
        wrapper = getattr(session, "_wrapper", None)
        client = getattr(session, "_client", None)
        if wrapper is not None and client is not None:
            try:
                wrapper.disconnect(client)
            except Exception:
                logger.debug("SessionManager: disconnect on evict failed")

    def create_session(self, session: LoginSession) -> str:
        self._evict_expired()
        login_id = self._generate_login_id()
        session.login_id = login_id
        with self._lock:
            self._sessions[login_id] = session
            self._created_at[login_id] = time.monotonic()

        logger.info(
            f"SessionManager: session created "
            f"login_id={login_id} user_id={session.user_id} phone={session.phone}"
        )

        return login_id

    def get_session(self, login_id: str) -> LoginSession:
        self._evict_expired()
        with self._lock:
            session = self._sessions.get(login_id)

        if session is None:
            logger.warning(f"SessionManager: session not found login_id={login_id}")
            raise LoginNotFoundError(login_id)

        return session

    def remove_session(self, login_id: str) -> LoginSession | None:
        with self._lock:
            self._created_at.pop(login_id, None)
            session = self._sessions.pop(login_id, None)

        if session:
            logger.info(
                f"SessionManager: session removed "
                f"login_id={login_id} user_id={session.user_id}"
            )
        else:
            logger.debug(
                f"SessionManager: session not found for removal login_id={login_id}"
            )

        return session

    def has_session(self, login_id: str) -> bool:
        with self._lock:
            return login_id in self._sessions

    def get_active_sessions_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _generate_login_id(self) -> str:
        login_id = secrets.token_urlsafe(16)
        logger.debug("SessionManager: generated login_id")
        return login_id
