# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from typing import Any


class TelegramAuthError(Exception):
    def __init__(self, message: str, error_code: str | None = None, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}


class LoginError(TelegramAuthError):
    pass


class SessionError(TelegramAuthError):
    pass


class StorageError(TelegramAuthError):
    pass


class RepositoryError(TelegramAuthError):
    pass


class EventLoopError(TelegramAuthError):
    pass


class ValidationError(TelegramAuthError):
    pass


class LoginNotFoundError(LoginError):
    def __init__(self, login_id: str):
        super().__init__(
            message=f"Login session not found: {login_id}",
            error_code="login_id_not_found",
            context={"login_id": login_id}
        )


class ApiProfileNotFoundError(LoginError):
    def __init__(self, user_id: int, api_profile_id: int):
        super().__init__(
            message=f"API Profile {api_profile_id} not found for user {user_id}",
            error_code="api_profile_not_found",
            context={"user_id": user_id, "api_profile_id": api_profile_id}
        )

