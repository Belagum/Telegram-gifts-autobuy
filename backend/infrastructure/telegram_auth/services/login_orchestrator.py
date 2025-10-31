# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from typing import Any

from backend.infrastructure.telegram_auth.exceptions import (
    ApiProfileNotFoundError,
    LoginError,
    LoginNotFoundError,
)
from backend.infrastructure.telegram_auth.interfaces.account_repository import (
    IAccountRepository,
)
from backend.infrastructure.telegram_auth.interfaces.event_loop import IEventLoop
from backend.infrastructure.telegram_auth.interfaces.session_storage import (
    ISessionStorage,
)
from backend.infrastructure.telegram_auth.models.dto import (
    LoginResult,
    LoginSession,
)
from backend.infrastructure.telegram_auth.services.pyrogram_client_wrapper import (
    PyrogramClientWrapper,
)
from backend.infrastructure.telegram_auth.services.session_manager import (
    SessionManager,
)
from backend.shared.logging import logger


class PyroLoginManager:
    def __init__(
        self,
        session_manager: SessionManager,
        session_storage: ISessionStorage,
        account_repository: IAccountRepository,
        event_loop: IEventLoop
    ) -> None:
        self._session_manager = session_manager
        self._session_storage = session_storage
        self._account_repository = account_repository
        self._event_loop = event_loop
        
        logger.debug("PyroLoginManager: initialized with dependencies")

    def start_login(
        self,
        user_id: int,
        api_profile_id: int,
        phone: str
    ) -> LoginResult:
        logger.info(
            f"PyroLoginManager: start_login "
            f"user_id={user_id} api_profile_id={api_profile_id} phone={phone}"
        )
        
        try:
            credentials = self._account_repository.get_api_credentials(
                user_id,
                api_profile_id
            )
            
            if not credentials:
                raise ApiProfileNotFoundError(user_id, api_profile_id)
            
            session_path = self._session_storage.get_session_path(user_id, phone)
            
            wrapper = PyrogramClientWrapper(
                session_path,
                credentials,
                self._event_loop
            )
            
            client, phone_code_hash = wrapper.connect_and_send_code(phone)
            
            login_session = LoginSession(
                login_id="",
                user_id=user_id,
                api_profile_id=api_profile_id,
                phone=phone,
                session_path=session_path,
                api_credentials=credentials,
                phone_code_hash=phone_code_hash
            )
            
            login_session._client = client
            login_session._wrapper = wrapper
            
            login_id = self._session_manager.create_session(login_session)
            
            logger.info(f"PyroLoginManager: start_login success login_id={login_id}")
            
            return LoginResult.ok(data={"login_id": login_id})
            
        except ApiProfileNotFoundError as e:
            return LoginResult.fail(
                error=e.message,
                error_code=e.error_code,
                data=e.context,
                http_status=400
            )
        except LoginError as e:
            is_telegram_error = e.error_code and e.error_code == e.error_code.upper()
            if is_telegram_error:
                self._cleanup_on_error(None, session_path if 'session_path' in locals() else None)
            return LoginResult.fail(
                error="telegram_rpc" if is_telegram_error else "unexpected",
                error_code=e.error_code,
                data=e.context,
                http_status=400,
                should_close_modal=True
            )
        except Exception:
            logger.exception(f"PyroLoginManager: start_login unexpected error user_id={user_id}")
            self._cleanup_on_error(None, session_path if 'session_path' in locals() else None)
            return LoginResult.fail(
                error="unexpected",
                error_code="start_login_failed",
                http_status=500,
                should_close_modal=True
            )

    def confirm_code(self, login_id: str, code: str) -> LoginResult:
        logger.info(f"PyroLoginManager: confirm_code login_id={login_id}")
        
        try:
            session = self._session_manager.get_session(login_id)
            
            client = getattr(session, "_client", None)
            wrapper: PyrogramClientWrapper = getattr(session, "_wrapper", None)
            
            if not client or not wrapper:
                raise LoginError("Session state corrupted", error_code="session_corrupted")
            
            success = wrapper.sign_in_with_code(
                client,
                session.phone,
                session.phone_code_hash or "",
                code
            )
            
            if not success:
                logger.info(f"PyroLoginManager: 2FA required login_id={login_id}")
                return LoginResult.ok(data={"need_2fa": True})
            
            account_data = wrapper.fetch_account_data()
            
            self._account_repository.save_account(
                user_id=session.user_id,
                api_profile_id=session.api_profile_id,
                phone=session.phone,
                session_path=session.session_path,
                account_data=account_data
            )
            
            self._cleanup_session(login_id, session, wrapper, client)
            
            logger.info(f"PyroLoginManager: confirm_code success login_id={login_id}")
            
            return LoginResult.ok()
            
        except LoginNotFoundError as e:
            return LoginResult.fail(
                error=e.message,
                error_code=e.error_code,
                data=e.context,
                http_status=400
            )
        except LoginError as e:
            is_telegram_error = e.error_code and e.error_code == e.error_code.upper()
            
            non_critical_codes = {"PHONE_CODE_INVALID"}
            is_non_critical = e.error_code in non_critical_codes
            
            if not is_non_critical:
                session = self._session_manager.remove_session(login_id)
                if session:
                    self._cleanup_on_error(session, session.session_path)
            
            return LoginResult.fail(
                error="telegram_rpc" if is_telegram_error else "unexpected",
                error_code=e.error_code,
                data=e.context,
                http_status=400,
                should_close_modal=not is_non_critical
            )
        except Exception:
            logger.exception(
                f"PyroLoginManager: confirm_code unexpected error login_id={login_id}"
            )
            session = self._session_manager.remove_session(login_id)
            if session:
                self._cleanup_on_error(session, session.session_path)
            return LoginResult.fail(
                error="unexpected",
                error_code="confirm_code_failed",
                http_status=500,
                should_close_modal=True
            )

    def confirm_password(self, login_id: str, password: str) -> LoginResult:
        logger.info(f"PyroLoginManager: confirm_password login_id={login_id}")
        
        try:
            session = self._session_manager.get_session(login_id)
            
            client = getattr(session, "_client", None)
            wrapper: PyrogramClientWrapper = getattr(session, "_wrapper", None)
            
            if not client or not wrapper:
                raise LoginError("Session state corrupted", error_code="session_corrupted")
            
            wrapper.confirm_2fa(client, password)
            
            account_data = wrapper.fetch_account_data()
            
            self._account_repository.save_account(
                user_id=session.user_id,
                api_profile_id=session.api_profile_id,
                phone=session.phone,
                session_path=session.session_path,
                account_data=account_data
            )
            
            self._cleanup_session(login_id, session, wrapper, client)
            
            logger.info(f"PyroLoginManager: confirm_password success login_id={login_id}")
            
            return LoginResult.ok()
            
        except LoginNotFoundError as e:
            return LoginResult.fail(
                error=e.message,
                error_code=e.error_code,
                data=e.context,
                http_status=400
            )
        except LoginError as e:
            is_telegram_error = e.error_code and e.error_code == e.error_code.upper()
            
            non_critical_codes = {"PASSWORD_HASH_INVALID"}
            is_non_critical = e.error_code in non_critical_codes
            
            if not is_non_critical:
                session = self._session_manager.remove_session(login_id)
                if session:
                    self._cleanup_on_error(session, session.session_path)
            
            return LoginResult.fail(
                error="telegram_rpc" if is_telegram_error else "unexpected",
                error_code=e.error_code,
                data=e.context,
                http_status=400,
                should_close_modal=not is_non_critical
            )
        except Exception:
            logger.exception(
                f"PyroLoginManager: confirm_password unexpected error login_id={login_id}"
            )
            session = self._session_manager.remove_session(login_id)
            if session:
                self._cleanup_on_error(session, session.session_path)
            return LoginResult.fail(
                error="unexpected",
                error_code="confirm_password_failed",
                http_status=500,
                should_close_modal=True
            )

    def cancel(self, login_id: str) -> LoginResult:
        logger.info(f"PyroLoginManager: cancel login_id={login_id}")
        
        session = self._session_manager.remove_session(login_id)
        
        if not session:
            logger.debug(f"PyroLoginManager: no session to cancel login_id={login_id}")
            return LoginResult.ok()
        
        client = getattr(session, "_client", None)
        wrapper: PyrogramClientWrapper | None = getattr(session, "_wrapper", None)
        
        if wrapper and client:
            self._cleanup_session(
                login_id,
                session,
                wrapper,
                client,
                purge_files=True
            )
        
        logger.info(f"PyroLoginManager: cancel done login_id={login_id}")
        
        return LoginResult.ok()

    def _cleanup_session(
        self,
        login_id: str,
        session: LoginSession,
        wrapper: PyrogramClientWrapper,
        client: Any,
        purge_files: bool = False
    ) -> None:
        logger.debug(
            f"PyroLoginManager: cleanup session "
            f"login_id={login_id} purge={purge_files}"
        )
        
        try:
            wrapper.disconnect(client)
        except Exception:
            logger.exception(f"PyroLoginManager: failed to disconnect client login_id={login_id}")
        
        if purge_files:
            try:
                self._session_storage.purge_session(session.session_path)
            except Exception:
                logger.exception(
                    f"PyroLoginManager: failed to purge session "
                    f"login_id={login_id} path={session.session_path}"
                )

    def _cleanup_on_error(
        self,
        session: LoginSession | None,
        session_path: str | None
    ) -> None:
        if session:
            client = getattr(session, "_client", None)
            wrapper: PyrogramClientWrapper | None = getattr(session, "_wrapper", None)
            
            if wrapper and client:
                try:
                    wrapper.disconnect(client)
                    logger.debug("PyroLoginManager: client disconnected during cleanup_on_error")
                except Exception:
                    logger.debug(
                        "PyroLoginManager: failed to disconnect client during cleanup_on_error"
                    )
        
        if session_path:
            try:
                self._session_storage.purge_session(session_path)
            except Exception:
                logger.exception(f"PyroLoginManager: cleanup_on_error failed path={session_path}")

