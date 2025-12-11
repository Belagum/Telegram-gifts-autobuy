# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from sqlalchemy.orm import Session

from backend.infrastructure.telegram_auth.repositories.sqlalchemy_account_repository import \
    SQLAlchemyAccountRepository
from backend.infrastructure.telegram_auth.services.event_loop_manager import \
    EventLoopManager
from backend.infrastructure.telegram_auth.services.login_orchestrator import \
    PyroLoginManager
from backend.infrastructure.telegram_auth.services.session_manager import \
    SessionManager
from backend.infrastructure.telegram_auth.storage.file_session_storage import \
    FileSessionStorage
from backend.shared.logging import logger


class LoginManagerFactory:
    @staticmethod
    def create(db_session: Session) -> PyroLoginManager:
        logger.debug("LoginManagerFactory: creating PyroLoginManager")

        session_manager = SessionManager()
        session_storage = FileSessionStorage()
        account_repository = SQLAlchemyAccountRepository(db_session)
        event_loop = EventLoopManager()

        login_manager = PyroLoginManager(
            session_manager=session_manager,
            session_storage=session_storage,
            account_repository=account_repository,
            event_loop=event_loop,
        )

        logger.debug("LoginManagerFactory: PyroLoginManager created")

        return login_manager


def create_login_manager(db_session: Session) -> PyroLoginManager:
    return LoginManagerFactory.create(db_session)
