# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from backend.domain import (AccountSnapshot, ChannelFilter, GiftCandidate,
                            PurchaseOperation)


@dataclass(slots=True)
class GiftPayload:
    raw: dict
    candidate: GiftCandidate


class AccountRepository(Protocol):
    def list_for_user(self, user_id: int) -> Sequence[AccountSnapshot]: ...


class ChannelRepository(Protocol):
    def list_for_user(self, user_id: int) -> Sequence[ChannelFilter]: ...


class UserSettingsRepository(Protocol):
    def get_bot_token(self, user_id: int) -> str | None: ...


class TelegramPort(Protocol):
    async def fetch_balance(self, account: AccountSnapshot) -> int: ...

    async def send_gift(
        self, operation: PurchaseOperation, account: AccountSnapshot
    ) -> None: ...

    async def resolve_self_ids(
        self, accounts: Iterable[AccountSnapshot]
    ) -> list[int]: ...


class NotificationPort(Protocol):
    async def send_reports(
        self, token: str, chat_ids: Sequence[int], messages: Sequence[str]
    ) -> None: ...
