# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import pytest

from backend.application.use_cases.users.login_user import LoginUserUseCase
from backend.domain.users.exceptions import InvalidCredentialsError


class _FakeHasher:
    def __init__(self):
        self.verify_calls = 0

    def hash(self, password: str) -> str:
        return f"hash:{password}"

    def verify(self, password: str, hashed: str) -> bool:
        self.verify_calls += 1
        return False


class _FakeUsers:
    def __init__(self, user=None):
        self._user = user

    def find_by_username(self, username: str):
        return self._user


class _FakeTokens:
    def replace_for_user(self, user_id: int):  # pragma: no cover - не вызывается
        raise AssertionError("token must not be issued on failed login")


def test_verify_runs_even_for_unknown_user():
    hasher = _FakeHasher()
    uc = LoginUserUseCase(users=_FakeUsers(None), tokens=_FakeTokens(), password_hasher=hasher)
    hasher.verify_calls = 0  # сбрасываем после dummy-hash в __init__
    with pytest.raises(InvalidCredentialsError):
        uc.execute("ghost_user_xyz", "whatever-password")
    # verify должен выполниться даже без пользователя — иначе утечка по таймингу
    assert hasher.verify_calls == 1
