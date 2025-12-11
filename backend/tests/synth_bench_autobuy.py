# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Synthetic benchmark for the Autobuy use-case."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from backend.application import AutobuyInput, AutobuyUseCase
from backend.application.interfaces import (AccountRepository,
                                            ChannelRepository,
                                            NotificationPort, TelegramPort,
                                            UserSettingsRepository)
from backend.domain import AccountSnapshot, ChannelFilter


@dataclass(slots=True)
class _StaticAccountRepo(AccountRepository):
    accounts: Sequence[AccountSnapshot]

    def list_for_user(self, user_id: int) -> Sequence[AccountSnapshot]:
        return list(self.accounts)


@dataclass(slots=True)
class _StaticChannelRepo(ChannelRepository):
    channels: Sequence[ChannelFilter]

    def list_for_user(self, user_id: int) -> Sequence[ChannelFilter]:
        return list(self.channels)


@dataclass(slots=True)
class _StaticSettingsRepo(UserSettingsRepository):
    token: str | None = "benchmark-token"

    def get_bot_token(self, user_id: int) -> str | None:
        return self.token


@dataclass(slots=True)
class _NullNotificationPort(NotificationPort):
    async def send_reports(
        self, token: str, chat_ids: Sequence[int], messages: Sequence[str]
    ) -> None:
        return None


@dataclass(slots=True)
class _StaticTelegramPort(TelegramPort):
    balances: dict[int, int]

    async def fetch_balance(self, account: AccountSnapshot) -> int:
        return self.balances.get(account.id, 0)

    async def send_gift(self, operation, account: AccountSnapshot) -> None:
        return None

    async def resolve_self_ids(self, accounts: Iterable[AccountSnapshot]) -> list[int]:
        return [account.id for account in accounts][:3]


def _generate_accounts(count: int) -> list[AccountSnapshot]:
    return [
        AccountSnapshot(
            id=i,
            user_id=1,
            session_path=f"/tmp/{i}",
            api_id=1000 + i,
            api_hash=f"hash-{i}",
            is_premium=True,
            balance=0,
        )
        for i in range(1, count + 1)
    ]


def _generate_channels(count: int) -> list[ChannelFilter]:
    return [
        ChannelFilter(
            id=i,
            user_id=1,
            channel_id=-1000000 - i,
            price_min=0,
            price_max=100,
            supply_min=None,
            supply_max=None,
        )
        for i in range(1, count + 1)
    ]


def _generate_gifts(count: int) -> list[dict[str, int | bool]]:
    gifts: list[dict[str, int | bool]] = []
    for i in range(1, count + 1):
        gifts.append(
            {
                "id": i,
                "price": 10 + (i % 5),
                "is_limited": True,
                "total_amount": 1000,
                "available_amount": 1000,
                "limited_per_user": False,
            }
        )
    return gifts


async def _run_once(
    accounts: Sequence[AccountSnapshot],
    channels: Sequence[ChannelFilter],
    gifts: Sequence[dict[str, int | bool]],
) -> float:
    telegram = _StaticTelegramPort({acc.id: 1000 for acc in accounts})
    use_case = AutobuyUseCase(
        accounts=_StaticAccountRepo(accounts),
        channels=_StaticChannelRepo(channels),
        telegram=telegram,
        notifications=_NullNotificationPort(),
        settings=_StaticSettingsRepo(),
    )
    start = time.perf_counter()
    await use_case.execute(AutobuyInput(user_id=1, gifts=list(gifts)))
    duration = time.perf_counter() - start
    return duration


async def _benchmark(iterations: int, acc_count: int, gift_count: int) -> list[float]:
    accounts = _generate_accounts(acc_count)
    channels = _generate_channels(max(1, acc_count // 2))
    gifts = _generate_gifts(gift_count)
    durations: list[float] = []
    for _ in range(iterations):
        durations.append(await _run_once(accounts, channels, gifts))
    return durations


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic Autobuy benchmark")
    parser.add_argument("--iterations", type=int, default=3, help="Number of runs")
    parser.add_argument("--accounts", type=int, default=100, help="Number of accounts")
    parser.add_argument("--gifts", type=int, default=200, help="Number of gifts")
    args = parser.parse_args()

    durations = asyncio.run(_benchmark(args.iterations, args.accounts, args.gifts))
    avg = statistics.mean(durations)
    p95 = statistics.quantiles(durations, n=20)[18] if len(durations) > 1 else avg
    ops = (args.accounts * args.gifts) / avg if avg > 0 else 0

    print(
        "Autobuy benchmark: "
        f"iterations={args.iterations} accounts={args.accounts} gifts={args.gifts}"
    )
    for idx, dur in enumerate(durations, start=1):
        print(f"  run {idx}: {dur:.4f} s")
    print(f"Average duration: {avg:.4f} s | P95: {p95:.4f} s | approx ops/s: {ops:.2f}")


if __name__ == "__main__":
    main()
