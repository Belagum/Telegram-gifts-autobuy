# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.domain.users.exceptions import InvalidCredentialsError
from backend.domain.users.repositories import PasswordHasher, SessionTokenRepository, UserRepository


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

    def execute(self, username: str, password: str) -> str:
        user = self._users.find_by_username(username)
        if not user or not self._password_hasher.verify(password, user.password_hash):
            raise InvalidCredentialsError()
        token = self._tokens.replace_for_user(user.id)
        return token.token
