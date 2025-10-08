"""Application service ports."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from backend.domain import (
    AccountSnapshot,
    ChannelFilter,
    GiftCandidate,
    PurchaseOperation,
)


@dataclass(slots=True)
class GiftPayload:
    """Validated external gift payload."""

    raw: dict
    candidate: GiftCandidate


class AccountRepository(Protocol):
    """Port for reading account snapshots."""

    def list_for_user(self, user_id: int) -> Sequence[AccountSnapshot]:
        """Return all accounts for the user sorted by id."""


class ChannelRepository(Protocol):
    """Port for reading channel filters."""

    def list_for_user(self, user_id: int) -> Sequence[ChannelFilter]: ...


class UserSettingsRepository(Protocol):
    """Port for retrieving user settings relevant for notifications."""

    def get_bot_token(self, user_id: int) -> str | None: ...


class TelegramPort(Protocol):
    """Port describing Telegram RPC interactions."""

    async def fetch_balance(self, account: AccountSnapshot) -> int: ...

    async def send_gift(self, operation: PurchaseOperation, account: AccountSnapshot) -> None: ...

    async def resolve_self_ids(self, accounts: Iterable[AccountSnapshot]) -> list[int]: ...


class NotificationPort(Protocol):
    """Port abstracting away notifications to Telegram."""

    async def send_reports(
        self, token: str, chat_ids: Sequence[int], messages: Sequence[str]
    ) -> None: ...
