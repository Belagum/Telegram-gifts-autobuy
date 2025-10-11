# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Domain entities that encapsulate GiftBuyer business rules."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .exceptions import InvariantViolation

INF_SUPPLY = 10**12


@dataclass(slots=True, frozen=True)
class ChannelFilter:
    """Channel purchase constraints owned by a user."""

    id: int
    user_id: int
    channel_id: int
    price_min: int | None
    price_max: int | None
    supply_min: int | None
    supply_max: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "channel_id", int(self.channel_id))
        if self.channel_id >= 0:
            raise InvariantViolation("channel id must be negative", field="channel_id")
        for fld in ("price_min", "price_max", "supply_min", "supply_max"):
            value = getattr(self, fld)
            if value is not None and value < 0:
                raise InvariantViolation("range bounds must be non-negative", field=fld)
        self._validate_range("price", self.price_min, self.price_max)
        self._validate_range("supply", self.supply_min, self.supply_max)

    @staticmethod
    def _validate_range(name: str, low: int | None, high: int | None) -> None:
        if low is not None and high is not None and low > high:
            raise InvariantViolation(f"{name} min must be <= {name} max", field=f"{name}_min")

    def matches(self, gift: GiftCandidate) -> bool:
        """Return whether the gift satisfies the configured constraints."""

        return all(
            [
                self._within(gift.price, self.price_min, self.price_max),
                self._within(gift.total_supply, self.supply_min, self.supply_max),
            ]
        )

    @staticmethod
    def _within(value: int, low: int | None, high: int | None) -> bool:
        if low is not None and value < low:
            return False
        if high is not None and value > high:
            return False
        return True


@dataclass(slots=True, frozen=True)
class GiftCandidate:
    """Gift exposed by Telegram that can potentially be purchased."""

    gift_id: int
    price: int
    total_supply: int
    available_amount: int
    per_user_cap: int
    require_premium: bool

    def __post_init__(self) -> None:
        if self.gift_id <= 0:
            raise InvariantViolation("gift id must be positive", field="gift_id")
        if self.price <= 0:
            raise InvariantViolation("price must be positive", field="price")
        if self.total_supply < 0:
            raise InvariantViolation("total supply must be >= 0", field="total_supply")
        if self.available_amount < 0:
            raise InvariantViolation("available amount must be >= 0", field="available_amount")
        if self.per_user_cap < 0:
            raise InvariantViolation("per user cap must be >= 0", field="per_user_cap")

    def priority_key(self) -> tuple[int, int, int]:
        """Lower key means higher priority."""

        supply = self.total_supply if self.total_supply > 0 else INF_SUPPLY
        return (supply, -self.price, self.gift_id)


@dataclass(slots=True)
class AccountSnapshot:
    """Immutable information about a Telegram account participating in autobuy."""

    id: int
    user_id: int
    session_path: str
    api_id: int
    api_hash: str
    is_premium: bool
    balance: int = field(default=0)

    def __post_init__(self) -> None:
        if self.balance < 0:
            raise InvariantViolation("balance cannot be negative", field="balance")

    def with_balance(self, balance: int) -> AccountSnapshot:
        if balance < 0:
            raise InvariantViolation("balance cannot be negative", field="balance")
        return AccountSnapshot(
            id=self.id,
            user_id=self.user_id,
            session_path=self.session_path,
            api_id=self.api_id,
            api_hash=self.api_hash,
            is_premium=self.is_premium,
            balance=balance,
        )

    def debit(self, amount: int) -> None:
        if amount < 0:
            raise InvariantViolation("debit amount cannot be negative", field="amount")
        if amount > self.balance:
            raise InvariantViolation("insufficient balance", field="amount")
        self.balance -= amount


@dataclass(slots=True, frozen=True)
class PurchaseOperation:
    """Single purchase request planned by the system."""

    account_id: int
    channel_id: int
    gift_id: int
    price: int
    supply: int

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise InvariantViolation("operation price must be positive", field="price")


@dataclass(slots=True)
class PurchasePlan:
    """A collection of operations with aggregate helpers (Unit of Work)."""

    operations: list[PurchaseOperation] = field(default_factory=list)

    def add(self, op: PurchaseOperation) -> None:
        self.operations.append(op)

    def extend(self, ops: Iterable[PurchaseOperation]) -> None:
        for op in ops:
            self.add(op)

    def __iter__(self):  # pragma: no cover - delegation
        return iter(self.operations)

    def __len__(self) -> int:  # pragma: no cover - delegation
        return len(self.operations)
