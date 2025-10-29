# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from typing import Protocol

from .entities import SessionToken, User


class UserRepository(Protocol):
    def find_by_username(self, username: str) -> User | None: ...
    def find_by_id(self, user_id: int) -> User | None: ...
    def add(self, user: User) -> User: ...


class SessionTokenRepository(Protocol):
    def replace_for_user(self, user_id: int) -> SessionToken: ...
    def revoke(self, token: str) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hashed: str) -> bool: ...
