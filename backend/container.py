# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Dependency container wiring infrastructure adapters."""

from __future__ import annotations

from functools import cached_property

from backend.application import AutobuyUseCase
from backend.application.interfaces import (
    AccountRepository,
    ChannelRepository,
    NotificationPort,
    TelegramPort,
    UserSettingsRepository,
)
from backend.config import load_config
from backend.db import SessionLocal
from backend.infrastructure.cache import InMemoryTTLCache
from backend.infrastructure.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyChannelRepository,
    SqlAlchemyUserSettingsRepository,
)
from backend.infrastructure.telegram import (
    TelegramNotificationAdapter,
    TelegramRpcPort,
)
from backend.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class Container:
    """Constructs and caches infrastructure adapters."""

    def __init__(self) -> None:
        self._config = load_config()
        self._session_factory = SessionLocal
        self._cache = InMemoryTTLCache[str, list[int]](self._config.cache.ttl_seconds)

    @cached_property
    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)

    @cached_property
    def account_repository(self) -> AccountRepository:
        return SqlAlchemyAccountRepository(self._session_factory)

    @cached_property
    def channel_repository(self) -> ChannelRepository:
        return SqlAlchemyChannelRepository(self._session_factory)

    @cached_property
    def settings_repository(self) -> UserSettingsRepository:
        return SqlAlchemyUserSettingsRepository(self._session_factory)

    @cached_property
    def telegram_port(self) -> TelegramPort:
        return TelegramRpcPort()

    @cached_property
    def notification_port(self) -> NotificationPort:
        return TelegramNotificationAdapter()

    @cached_property
    def autobuy_use_case(self) -> AutobuyUseCase:
        return AutobuyUseCase(
            accounts=self.account_repository,
            channels=self.channel_repository,
            telegram=self.telegram_port,
            notifications=self.notification_port,
            settings=self.settings_repository,
        )


container = Container()
