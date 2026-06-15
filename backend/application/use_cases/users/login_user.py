# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from http import HTTPStatus

from backend.domain.users.exceptions import InvalidCredentialsError
from backend.domain.users.repositories import (PasswordHasher,
                                               SessionTokenRepository,
                                               UserRepository)
from backend.infrastructure.auth.login_attempts import (is_account_locked,
                                                        record_login_attempt)
from backend.shared.errors.base import AppError


class AccountLockedError(AppError):
    def __init__(self, lockout_remaining: float = 0) -> None:
        super().__init__(
            code="account_locked",
            status=HTTPStatus.TOO_MANY_REQUESTS,
            context={"lockout_remaining_seconds": round(lockout_remaining, 1)},
        )


class LoginUserUseCase:
    def __init__(
        self,
        *,
        users: UserRepository,
        tokens: SessionTokenRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._password_hasher = password_hasher
        # Фейковый хэш для несуществующих пользователей: verify выполняется всегда
        # одинаковым алгоритмом, чтобы время ответа не выдавало существование логина.
        self._dummy_hash = password_hasher.hash("timing-attack-dummy-password")

    def execute(
        self, username: str, password: str, ip_address: str | None = None
    ) -> str:
        if is_account_locked(username):
            from backend.infrastructure.auth.login_attempts import \
                get_lockout_remaining

            remaining = get_lockout_remaining(username)
            raise AccountLockedError(lockout_remaining=remaining)

        user = self._users.find_by_username(username)

        password_hash = user.password_hash if user is not None else self._dummy_hash
        password_ok = self._password_hasher.verify(password, password_hash)

        if user is None or not password_ok:
            record_login_attempt(username, success=False, ip_address=ip_address)
            raise InvalidCredentialsError()

        record_login_attempt(username, success=True, ip_address=ip_address)

        token = self._tokens.replace_for_user(user.id)
        return token.token
