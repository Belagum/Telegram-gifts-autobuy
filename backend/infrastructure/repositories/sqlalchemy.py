# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from collections.abc import Callable, Sequence

from backend.application import (
    AccountRepository,
    ChannelRepository,
    UserSettingsRepository,
)
from backend.domain import AccountSnapshot, ChannelFilter
from backend.infrastructure.db.models import Account, Channel, UserSettings
from backend.infrastructure.unit_of_work import unit_of_work_scope
from sqlalchemy.orm import Session, joinedload


class SqlAlchemyAccountRepository(AccountRepository):
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def list_for_user(self, user_id: int) -> Sequence[AccountSnapshot]:
        with unit_of_work_scope(self._session_factory) as session:
            rows = (
                session.query(Account)
                .options(joinedload(Account.api_profile))
                .filter(Account.user_id == user_id)
                .order_by(Account.id.asc())
                .all()
            )
        return [
            AccountSnapshot(
                id=row.id,
                user_id=row.user_id,
                session_path=row.session_path,
                api_id=row.api_profile.api_id,
                api_hash=row.api_profile.api_hash,
                is_premium=bool(row.is_premium),
                balance=max(int(row.stars_amount or 0), 0),
            )
            for row in rows
        ]


class SqlAlchemyChannelRepository(ChannelRepository):
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def list_for_user(self, user_id: int) -> Sequence[ChannelFilter]:
        with unit_of_work_scope(self._session_factory) as session:
            rows = (
                session.query(Channel)
                .filter(Channel.user_id == user_id)
                .order_by(Channel.id.asc())
                .all()
            )
        return [
            ChannelFilter(
                id=row.id,
                user_id=row.user_id,
                channel_id=int(row.channel_id),
                price_min=int(row.price_min) if row.price_min is not None else None,
                price_max=int(row.price_max) if row.price_max is not None else None,
                supply_min=int(row.supply_min) if row.supply_min is not None else None,
                supply_max=int(row.supply_max) if row.supply_max is not None else None,
            )
            for row in rows
        ]


class SqlAlchemyUserSettingsRepository(UserSettingsRepository):
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def get_bot_token(self, user_id: int) -> str | None:
        with unit_of_work_scope(self._session_factory) as session:
            settings = session.get(UserSettings, user_id)
            if not settings:
                return None
            token = getattr(settings, "bot_token", None)
            return token.strip() if token else None
