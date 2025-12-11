# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import secrets

from backend.infrastructure.telegram_auth.exceptions import LoginNotFoundError
from backend.infrastructure.telegram_auth.models.dto import LoginSession
from backend.shared.logging import logger


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, LoginSession] = {}
        logger.debug("SessionManager: initialized")

    def create_session(self, session: LoginSession) -> str:
        login_id = self._generate_login_id()
        session.login_id = login_id
        self._sessions[login_id] = session

        logger.info(
            f"SessionManager: session created "
            f"login_id={login_id} user_id={session.user_id} phone={session.phone}"
        )

        return login_id

    def get_session(self, login_id: str) -> LoginSession:
        session = self._sessions.get(login_id)

        if session is None:
            logger.warning(f"SessionManager: session not found login_id={login_id}")
            raise LoginNotFoundError(login_id)

        return session

    def remove_session(self, login_id: str) -> LoginSession | None:
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
        return login_id in self._sessions

    def get_active_sessions_count(self) -> int:
        return len(self._sessions)

    def _generate_login_id(self) -> str:
        login_id = secrets.token_urlsafe(16)
        logger.debug(f"SessionManager: generated login_id={login_id}")
        return login_id
