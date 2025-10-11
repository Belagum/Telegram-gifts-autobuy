# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from datetime import UTC, datetime

from backend.domain.users.entities import User
from backend.domain.users.exceptions import UserAlreadyExistsError
from backend.domain.users.repositories import PasswordHasher, SessionTokenRepository, UserRepository


class RegisterUserUseCase:
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

    def execute(self, username: str, password: str) -> tuple[User, str]:
        existing = self._users.find_by_username(username)
        if existing:
            raise UserAlreadyExistsError()
        now = datetime.now(UTC)
        hashed = self._password_hasher.hash(password)
        user = User(id=0, username=username, password_hash=hashed, created_at=now)
        persisted = self._users.add(user)
        token = self._tokens.replace_for_user(persisted.id)
        return persisted, token.token
