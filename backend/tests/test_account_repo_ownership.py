# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import pytest

from backend.infrastructure.telegram_auth.exceptions import RepositoryError
from backend.infrastructure.telegram_auth.repositories.sqlalchemy_account_repository import \
    SQLAlchemyAccountRepository


class _FakeAccount:
    def __init__(self, user_id: int):
        self.user_id = user_id


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _FakeDb:
    def __init__(self, pk_account):
        self._pk_account = pk_account

    def query(self, *args, **kwargs):
        return _FakeQuery()

    def get(self, model, pk):
        return self._pk_account


def test_find_existing_rejects_other_users_telegram_id():
    repo = SQLAlchemyAccountRepository(_FakeDb(_FakeAccount(user_id=1)))
    with pytest.raises(RepositoryError):
        repo._find_existing_account(user_id=2, phone="+7", telegram_id=999)


def test_find_existing_allows_same_user_telegram_id():
    same = _FakeAccount(user_id=1)
    repo = SQLAlchemyAccountRepository(_FakeDb(same))
    assert repo._find_existing_account(user_id=1, phone="+7", telegram_id=999) is same
