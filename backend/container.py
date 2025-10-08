"""Simple dependency injection container."""

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
from backend.db import SessionLocal
from backend.infrastructure.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyChannelRepository,
    SqlAlchemyUserSettingsRepository,
)
from backend.infrastructure.telegram import (
    TelegramNotificationAdapter,
    TelegramRpcPort,
)


class Container:
    """Constructs and caches infrastructure adapters."""

    def __init__(self) -> None:
        self._session_factory = SessionLocal

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
