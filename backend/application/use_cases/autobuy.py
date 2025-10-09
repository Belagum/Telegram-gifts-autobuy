# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Autobuy use-case implemented in object oriented style."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from backend.domain import (
    AccountSnapshot,
    ChannelFilter,
    GiftCandidate,
    PurchaseOperation,
    PurchasePlan,
)
from backend.logger import logger

from ..interfaces import (
    AccountRepository,
    ChannelRepository,
    GiftPayload,
    NotificationPort,
    TelegramPort,
    UserSettingsRepository,
)

_INF_SUPPLY = 10**12


@dataclass(slots=True)
class AutobuyInput:
    user_id: int
    gifts: Sequence[dict[str, Any]]
    forced_channel_id: int | None = None


@dataclass(slots=True)
class AutobuyOutput:
    purchased: list[dict[str, Any]]
    skipped: int
    stats: dict[str, Any]


class AutobuyStats:
    """Mutable aggregate of autobuy execution metrics."""

    def __init__(self, channels: Sequence[ChannelFilter], accounts: Sequence[AccountSnapshot]):
        self._channels: dict[int, dict[str, Any]] = {
            c.channel_id: {
                "row_id": c.id,
                "purchased": [],
                "failed": [],
                "reasons": [],
                "planned": 0,
            }
            for c in channels
        }
        self._accounts: dict[int, dict[str, Any]] = {
            a.id: {
                "balance_start": a.balance,
                "balance_end": a.balance,
                "spent": 0,
                "purchases": 0,
                "planned": 0,
            }
            for a in accounts
        }
        self._global_skips: list[dict[str, Any]] = []
        self._plan_skips: list[dict[str, Any]] = []
        self.plan: PurchasePlan = PurchasePlan()
        self._deferred: list[dict[str, Any]] = []

    def record_global_skip(
        self, gift_id: int, reason: str, *, details: Sequence[str] | None = None
    ) -> None:
        self._global_skips.append(
            {"gift_id": gift_id, "reason": reason, "details": list(details or [])}
        )

    def record_plan_skip(
        self, gift_id: int, reason: str, *, details: Sequence[str] | None = None
    ) -> None:
        self._plan_skips.append(
            {"gift_id": gift_id, "reason": reason, "details": list(details or [])}
        )

    def record_planned(self, op: PurchaseOperation) -> None:
        self.plan.add(op)
        ch = self._channels.setdefault(
            op.channel_id,
            {
                "row_id": None,
                "purchased": [],
                "failed": [],
                "reasons": [],
                "planned": 0,
            },
        )
        ch["planned"] += 1
        acc = self._accounts.setdefault(
            op.account_id,
            {
                "balance_start": 0,
                "balance_end": 0,
                "spent": 0,
                "purchases": 0,
                "planned": 0,
            },
        )
        acc["planned"] += 1

    def record_deferred(self, op: PurchaseOperation, *, available_at: datetime) -> None:
        payload = {
            "gift_id": op.gift_id,
            "price": op.price,
            "account_id": op.account_id,
            "channel_id": op.channel_id,
            "available_at": available_at.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        self._deferred.append(payload)

    def record_purchase(self, op: PurchaseOperation, *, balance_after: int, supply: int) -> None:
        purchased = {
            "gift_id": op.gift_id,
            "price": op.price,
            "supply": supply,
            "account_id": op.account_id,
        }
        self._channels[op.channel_id]["purchased"].append(purchased)
        acc = self._accounts[op.account_id]
        acc["spent"] += op.price
        acc["purchases"] += 1
        acc["balance_end"] = balance_after

    def record_failure(
        self,
        op: PurchaseOperation,
        *,
        reason: str,
        balance: int | None = None,
        need: int | None = None,
        rpc: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "gift_id": op.gift_id,
            "price": op.price,
            "account_id": op.account_id,
            "reason": reason,
        }
        if balance is not None:
            payload["balance"] = balance
        if need is not None:
            payload["need"] = need
        if rpc is not None:
            payload["rpc"] = rpc
        self._channels.setdefault(
            op.channel_id,
            {
                "row_id": None,
                "purchased": [],
                "failed": [],
                "reasons": [],
                "planned": 0,
            },
        )["failed"].append(payload)

    def record_reason(
        self,
        op: PurchaseOperation,
        *,
        reason: str,
        balance: int | None = None,
        need: int | None = None,
    ) -> None:
        payload = {
            "gift_id": op.gift_id,
            "price": op.price,
            "account_id": op.account_id,
            "reason": reason,
        }
        if balance is not None:
            payload["balance"] = balance
        if need is not None:
            payload["need"] = need
        self._channels.setdefault(
            op.channel_id,
            {
                "row_id": None,
                "purchased": [],
                "failed": [],
                "reasons": [],
                "planned": 0,
            },
        )["reasons"].append(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channels": self._channels,
            "accounts": self._accounts,
            "global_skips": self._global_skips,
            "plan_skips": self._plan_skips,
            "plan": [asdict(op) for op in self.plan],
            "deferred": list(self._deferred),
        }


class GiftValidator:
    """Boundary validation for raw gift payloads."""

    def __init__(self, *, require_limited: bool = True):
        self.require_limited = require_limited

    def validate_many(
        self, gifts: Sequence[dict]
    ) -> tuple[list[GiftPayload], list[dict[str, Any]]]:
        payloads: list[GiftPayload] = []
        skipped: list[dict[str, Any]] = []
        for item in gifts:
            try:
                candidate = self._to_candidate(item)
            except GiftRejectedError as exc:
                skipped.append(
                    {
                        "gift_id": int(item.get("id") or 0),
                        "reason": exc.reason,
                        "details": exc.details,
                    }
                )
                continue
            payloads.append(GiftPayload(raw=item, candidate=candidate))
        payloads.sort(key=lambda g: g.candidate.priority_key())
        return payloads, skipped

    def _to_candidate(self, data: dict) -> GiftCandidate:
        gift_id = int(data.get("id", 0) or 0)
        if gift_id <= 0:
            raise GiftRejectedError("invalid/id")
        price = int(data.get("price", 0) or 0)
        if price <= 0:
            raise GiftRejectedError("invalid/price")
        supply_raw = data.get("total_amount")
        if supply_raw is None:
            raise GiftRejectedError("no_supply_for_limited")
        total_supply = int(supply_raw or 0)
        available_raw = data.get("available_amount")
        available = int(available_raw or 0)
        limited = bool(data.get("is_limited"))
        if self.require_limited and not limited:
            raise GiftRejectedError("unlimited")
        per_user_cap = self._resolve_per_user_cap(data)
        require_premium = bool(data.get("require_premium"))
        return GiftCandidate(
            gift_id=gift_id,
            price=price,
            total_supply=total_supply,
            available_amount=available,
            per_user_cap=per_user_cap,
            require_premium=require_premium,
        )

    @staticmethod
    def _resolve_per_user_cap(data: dict) -> int:
        if bool(data.get("limited_per_user")):
            value = data.get("per_user_available") or data.get("per_user_remains")
            return max(int(value or 0), 0)
        return _INF_SUPPLY


class GiftRejectedError(Exception):
    """Represents a validation failure that should be reported as a skip."""

    def __init__(self, reason: str, details: Sequence[str] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.details = list(details or [])


class ChannelSelector:
    """Strategy object that finds a best matching channel for a gift."""

    def __init__(self, channels: Sequence[ChannelFilter]):
        self._channels = list(channels)

    def best_for(
        self, gift: GiftCandidate, forced_channel_id: int | None = None
    ) -> ChannelFilter | None:
        if forced_channel_id is not None:
            return next((c for c in self._channels if c.channel_id == forced_channel_id), None)
        matching = [c for c in self._channels if c.matches(gift)]
        if not matching:
            return None
        matching.sort(key=self._priority_key)
        return matching[0]

    @staticmethod
    def _priority_key(channel: ChannelFilter) -> tuple[int, int, int]:
        supply_range = (channel.supply_max or _INF_SUPPLY) - (channel.supply_min or 0)
        price_priority = -(channel.price_max or 0)
        return (supply_range, price_priority, channel.id)


class PurchasePlanner:
    """Generates a purchase plan using available balances and channel constraints."""

    def __init__(
        self,
        selector: ChannelSelector,
        stats: AutobuyStats,
        lock_resolver: LockStatusResolver,
    ):
        self._selector = selector
        self._stats = stats
        self._lock_resolver = lock_resolver

    def plan(
        self,
        *,
        accounts: Sequence[AccountSnapshot],
        gifts: Sequence[GiftPayload],
        stars: dict[int, int],
        forced_channel_id: int | None = None,
    ) -> PurchaseSchedule:
        remain_by_gift: dict[int, int] = {
            p.candidate.gift_id: p.candidate.available_amount for p in gifts
        }
        already_by_account: dict[tuple[int, int], int] = {}
        deferred: list[DeferredPurchase] = []
        for account in sorted(accounts, key=lambda a: stars.get(a.id, 0), reverse=True):
            budget = stars.get(account.id, 0)
            if budget <= 0:
                continue
            for payload in gifts:
                candidate = payload.candidate
                gift_id = candidate.gift_id
                price = candidate.price
                if remain_by_gift.get(gift_id, 0) <= 0:
                    continue
                channel = self._selector.best_for(candidate, forced_channel_id)
                if channel is None:
                    if forced_channel_id is None:
                        self._stats.record_plan_skip(
                            gift_id,
                            "no_channel_match",
                            details=[f"supply={candidate.total_supply} price={candidate.price}"],
                        )
                        continue
                    target_channel_id = forced_channel_id
                else:
                    target_channel_id = channel.channel_id
                cap_total = candidate.per_user_cap
                already = already_by_account.get((account.id, gift_id), 0)
                cap_left = max(0, cap_total - already)
                if cap_left <= 0:
                    self._stats.record_plan_skip(
                        gift_id,
                        "per_user_cap_reached",
                        details=[f"acc={account.id} cap={cap_total}"],
                    )
                    continue
                lock_status = self._lock_resolver.for_account(account.id, payload)
                if lock_status.locked and lock_status.available_at is not None:
                    op = PurchaseOperation(
                        account_id=account.id,
                        channel_id=target_channel_id,
                        gift_id=gift_id,
                        price=price,
                        supply=candidate.total_supply,
                    )
                    deferred.append(
                        DeferredPurchase(operation=op, available_at=lock_status.available_at)
                    )
                    self._stats.record_deferred(op, available_at=lock_status.available_at)
                    continue
                max_qty = min(remain_by_gift[gift_id], budget // price, cap_left)
                if max_qty <= 0:
                    if budget < price:
                        self._stats.record_plan_skip(
                            gift_id,
                            "not_enough_stars_account",
                            details=[f"acc={account.id} bal={budget} need={price}"],
                        )
                    continue
                # ``forced_channel_id`` is used to emulate legacy behaviour when the
                # user directs all purchases into a single channel. In this mode we
                # still record statistics under that synthetic channel even if it is
                # absent from the configured list.
                for _ in range(int(max_qty)):
                    op = PurchaseOperation(
                        account_id=account.id,
                        channel_id=target_channel_id,
                        gift_id=gift_id,
                        price=price,
                        supply=candidate.total_supply,
                    )
                    self._stats.record_planned(op)
                    budget -= price
                    remain_by_gift[gift_id] -= 1
                    already += 1
                    already_by_account[(account.id, gift_id)] = already
                    if budget < price or remain_by_gift[gift_id] <= 0 or already >= cap_total:
                        break
        return PurchaseSchedule(plan=self._stats.plan, deferred=deferred)


@dataclass(slots=True, frozen=True)
class LockStatus:
    locked: bool
    available_at: datetime | None


class LockStatusResolver:
    """Resolves per-account gift lock information."""

    def __init__(self, now_factory: Callable[[], datetime]):
        self._now_factory = now_factory

    def for_account(self, account_id: int, payload: GiftPayload) -> LockStatus:
        locks_raw = payload.raw.get("locked_until_by_account")
        lock_value: Any | None = None
        if isinstance(locks_raw, dict):
            lock_value = locks_raw.get(account_id)
            if lock_value is None:
                lock_value = locks_raw.get(str(account_id))
        if lock_value is None:
            lock_value = payload.raw.get("locked_until_date")
        available_at = self._parse(lock_value)
        if available_at is None:
            return LockStatus(locked=False, available_at=None)
        now = self._now_factory()
        if available_at <= now:
            return LockStatus(locked=False, available_at=None)
        return LockStatus(locked=True, available_at=available_at)

    @staticmethod
    def _parse(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(UTC)
        if isinstance(value, (int | float)):
            return datetime.fromtimestamp(int(value), tz=UTC)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            normalised = f"{text[:-1]}+00:00" if text.endswith("Z") else text
            try:
                parsed = datetime.fromisoformat(normalised)
            except ValueError:
                return None
            return (
                parsed.replace(tzinfo=UTC)
                if parsed.tzinfo is None
                else parsed.astimezone(UTC)
            )
        return None


@dataclass(slots=True)
class DeferredPurchase:
    operation: PurchaseOperation
    available_at: datetime


@dataclass(slots=True)
class PurchaseSchedule:
    plan: PurchasePlan
    deferred: list[DeferredPurchase]


class ReportBuilder:
    """Renders human readable reports that mirror legacy behaviour."""

    HEADER = "🧾"
    OK = "✅"
    SKIP = "⏭️"
    FAIL = "❌"
    STAR = "⭐"
    BOX = "📦"
    CHANNEL = "🛰️"
    ACCOUNT = "👤"
    COIN = "💰"
    CHART = "📊"

    def build(self, stats: dict, considered: Sequence[dict]) -> list[str]:
        lines: list[str] = []
        lines.append(f"{self.HEADER} Отчёт автопокупки")
        total = len(considered)
        bought = sum(len(ch["purchased"]) for ch in stats.get("channels", {}).values())
        skipped = total - bought
        lines.append(f"{self.CHART} Новых: {total} | Куплено: {bought} | Пропущено: {skipped}")
        if stats.get("plan_skips"):
            lines.append(f"{self.SKIP} Пропуски на этапе планирования: {len(stats['plan_skips'])}")
        lines.append("")
        lines.append(f"{self.BOX} По подаркам:")
        purchased_map: dict[int, list[dict]] = {}
        for cid, channel in stats.get("channels", {}).items():
            for row in channel.get("purchased", []):
                purchased_map.setdefault(int(row.get("gift_id", 0)), []).append(
                    row | {"channel_id": int(cid)}
                )
        failures: dict[int, list[dict]] = {}
        reasons: dict[int, list[dict]] = {}
        for cid, channel in stats.get("channels", {}).items():
            for row in channel.get("failed", []):
                failures.setdefault(int(row.get("gift_id", 0)), []).append({"cid": int(cid), **row})
            for row in channel.get("reasons", []):
                reasons.setdefault(int(row.get("gift_id", 0)), []).append({"cid": int(cid), **row})
        global_skips = {int(row.get("gift_id", 0)): row for row in stats.get("global_skips", [])}
        plan_skips: dict[int, list[dict]] = {}
        for row in stats.get("plan_skips", []):
            plan_skips.setdefault(int(row.get("gift_id", 0)), []).append(row)
        for gift in considered:
            gid = int(gift.get("id", 0))
            price = int(gift.get("price", 0))
            supply_raw = gift.get("total_amount")
            supply_str = "∞" if supply_raw is None else str(supply_raw)
            avail = gift.get("available_amount")
            if gid in purchased_map:
                for row in purchased_map[gid]:
                    lines.append(
                        f"• {self.OK} {gid} | {price}{self.STAR} | supply={supply_str} "
                        f"→ ch={row.get('channel_id')} acc={row.get('account_id')}"
                    )
                continue
            if gid in global_skips:
                payload = global_skips[gid]
                details = payload.get("details") or []
                detail_txt = f" [{', '.join(map(str, details))}]" if details else ""
                base = (
                    f"• {self.SKIP} {gid} | {price}{self.STAR} | supply={supply_str} "
                    f"→ {payload.get('reason')}"
                )
                lines.append(base + detail_txt)
                continue
            printed_header = False
            if gid in reasons:
                printed_header = True
                lines.append(f"• {self.FAIL} {gid} | {price}{self.STAR} | supply={supply_str}")
                for row in reasons[gid][:5]:
                    reason_line = (
                        f"   — причина ch={row['cid']}: {row.get('reason')} "
                        f"acc={row.get('account_id')} bal={row.get('balance')} "
                        f"need={row.get('need')}"
                    )
                    lines.append(reason_line)
            if gid in failures:
                if not printed_header:
                    lines.append(f"• {self.FAIL} {gid} | {price}{self.STAR} | supply={supply_str}")
                    printed_header = True
                for row in failures[gid][:5]:
                    rpc = row.get("rpc")
                    rpc_txt = (
                        f" ({rpc.get('code')} | {rpc.get('message')})"
                        if isinstance(rpc, dict)
                        else ""
                    )
                    lines.append(
                        f"   — ошибка ch={row['cid']}: send_gift_failed "
                        f"acc={row.get('account_id')}{rpc_txt}"
                    )
            if gid in plan_skips:
                if not printed_header:
                    lines.append(f"• {self.SKIP} {gid} | {price}{self.STAR} | supply={supply_str}")
                    printed_header = True
                for row in plan_skips[gid][:5]:
                    details = row.get("details")
                    suffix = f" ({'; '.join(map(str, details))})" if details else ""
                    lines.append(f"   — план: {row.get('reason')}{suffix}")
            if not printed_header and isinstance(avail, int) and avail <= 0:
                lines.append(
                    f"• {self.SKIP} {gid} | {price}{self.STAR} | supply={supply_str} "
                    "→ not_available (avail=0)"
                )
                printed_header = True
            if not printed_header:
                lines.append(
                    f"• {self.FAIL} {gid} | {price}{self.STAR} | supply={supply_str} (нет данных)"
                )
        lines.append("")
        deferred_rows = stats.get("deferred") or []
        if deferred_rows:
            lines.append("⏳ Отложенные покупки:")
            for row in deferred_rows:
                pending = (
                    f"• подарок {row.get('gift_id')} → acc={row.get('account_id')} "
                    f"ch={row.get('channel_id')} будет куплен "
                    f"{row.get('available_at')} (лок истечёт)"
                )
                lines.append(pending)
            lines.append("")
        lines.append(f"{self.CHANNEL} По каналам:")
        for cid, st in stats.get("channels", {}).items():
            lines.append(
                f"• {cid}: plan={st.get('planned', 0)} ok={len(st.get('purchased', []))} "
                f"fail={len(st.get('failed', []))} reasons={len(st.get('reasons', []))}"
            )
        lines.append("")
        lines.append(f"{self.ACCOUNT} По аккаунтам:")
        for aid, st in stats.get("accounts", {}).items():
            lines.append(
                f"• acc={aid}: plan={st.get('planned', 0)} {self.COIN}spent={st.get('spent', 0)} "
                f"start={st.get('balance_start', 0)} end={st.get('balance_end', 0)} "
                f"buys={st.get('purchases', 0)}"
            )
        tail = [
            x
            for x in (stats.get("plan_skips") or [])
            if int(x.get("gift_id") or 0) not in purchased_map
        ]
        if tail:
            lines.append("")
            lines.append(f"{self.SKIP} Итого пропуски планирования: {len(tail)}")
        return lines


class AutobuyUseCase:
    """Coordinates the autobuy process end-to-end."""

    def __init__(
        self,
        *,
        accounts: AccountRepository,
        channels: ChannelRepository,
        telegram: TelegramPort,
        notifications: NotificationPort,
        settings: UserSettingsRepository,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._accounts = accounts
        self._channels = channels
        self._telegram = telegram
        self._notifications = notifications
        self._settings = settings
        self._validator = GiftValidator()
        self._report = ReportBuilder()
        self._clock = now_factory or (lambda: datetime.now(UTC))
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def execute(self, data: AutobuyInput) -> AutobuyOutput:
        logger.bind(user_id=data.user_id).info(f"autobuy:start gifts={len(data.gifts)}")
        gifts, skipped_rows = self._validator.validate_many(data.gifts)
        accounts = list(self._accounts.list_for_user(data.user_id))
        if not accounts:
            logger.info(f"autobuy:no_accounts user_id={data.user_id}")
            early_stats = self._empty_stats(skipped_rows)
            early_stats["global_skips"].append({"reason": "no_accounts"})
            return AutobuyOutput(purchased=[], skipped=len(data.gifts), stats=early_stats)
        channels = list(self._channels.list_for_user(data.user_id))
        if data.forced_channel_id is None and not channels:
            logger.info(f"autobuy:no_channels user_id={data.user_id}")
            early_stats = self._empty_stats(skipped_rows)
            early_stats["global_skips"].append({"reason": "no_channels"})
            return AutobuyOutput(purchased=[], skipped=len(data.gifts), stats=early_stats)
        selector = ChannelSelector(channels)
        enriched_accounts = await self._load_balances(accounts)
        stats = AutobuyStats(channels, enriched_accounts)
        for row in skipped_rows:
            stats.record_global_skip(
                row.get("gift_id", 0),
                row.get("reason", "invalid"),
                details=row.get("details") or [],
            )
        stars = {acc.id: acc.balance for acc in enriched_accounts}
        total_stars = sum(stars.values())
        balances = ", ".join(f"{aid}:{bal}" for aid, bal in stars.items())
        logger.bind(user_id=data.user_id).info(
            f"autobuy:balances total={total_stars} details={balances}"
        )
        lock_resolver = LockStatusResolver(self._clock)
        planner = PurchasePlanner(selector, stats, lock_resolver)
        schedule = planner.plan(
            accounts=enriched_accounts,
            gifts=gifts,
            stars=stars,
            forced_channel_id=data.forced_channel_id,
        )
        await self._execute_plan(schedule.plan, enriched_accounts, stats)
        accounts_map = {acc.id: acc for acc in enriched_accounts}
        self._schedule_deferred(schedule.deferred, accounts_map, stats)
        stats_dict = stats.to_dict()
        purchased: list[dict] = []
        for cid, st in stats_dict["channels"].items():
            for row in st["purchased"]:
                purchased.append(
                    {
                        "gift_id": row["gift_id"],
                        "price": row["price"],
                        "supply": row.get("supply"),
                        "channel_id": cid,
                        "channel_row_id": st["row_id"],
                        "account_id": row["account_id"],
                    }
                )
        skipped = len(data.gifts) - len(purchased)
        await self._send_reports(data.user_id, stats_dict, list(data.gifts))
        summary_line = (
            f"autobuy:summary purchased={len(purchased)} skipped={skipped} "
            f"plan={len(schedule.plan)} deferred={len(schedule.deferred)}"
        )
        logger.bind(user_id=data.user_id).info(summary_line)
        return AutobuyOutput(purchased=purchased, skipped=skipped, stats=stats_dict)

    @staticmethod
    def _empty_stats(skipped_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
        return {
            "channels": {},
            "accounts": {},
            "global_skips": [dict(row) for row in skipped_rows],
            "plan_skips": [],
            "plan": [],
            "deferred": [],
        }

    async def _load_balances(self, accounts: Sequence[AccountSnapshot]) -> list[AccountSnapshot]:
        enriched: list[AccountSnapshot] = []
        for account in accounts:
            try:
                balance = await self._telegram.fetch_balance(account)
            except Exception as exc:  # pragma: no cover - network failure branch
                logger.opt(exception=exc).debug(f"autobuy:balance_fail account_id={account.id}")
                balance = 0
            enriched.append(account.with_balance(balance))
        return enriched

    async def _execute_plan(
        self,
        plan: PurchasePlan,
        accounts: Sequence[AccountSnapshot],
        stats: AutobuyStats,
    ) -> None:
        accounts_map = {acc.id: acc for acc in accounts}
        for op in plan:
            account = accounts_map[op.account_id]
            if account.balance < op.price:
                stats.record_reason(
                    op,
                    reason="insufficient_account_balance",
                    balance=account.balance,
                    need=op.price,
                )
                continue
            try:
                await self._telegram.send_gift(op, account)
                account.balance -= op.price
                stats.record_purchase(op, balance_after=account.balance, supply=op.supply)
            except Exception as exc:  # pragma: no cover - network failure branch
                reason = {"code": type(exc).__name__, "message": str(exc)[:400]}
                stats.record_failure(op, reason="send_gift_failed", rpc=reason)
                logger.opt(exception=exc).warning(
                    f"autobuy:send_fail account_id={op.account_id} channel={op.channel_id} "
                    f"gift={op.gift_id} reason={reason}"
                )
            await asyncio.sleep(0)

    def _schedule_deferred(
        self,
        deferred: Sequence[DeferredPurchase],
        accounts_map: dict[int, AccountSnapshot],
        stats: AutobuyStats,
    ) -> None:
        for item in deferred:
            task = asyncio.create_task(self._wait_and_purchase(item, accounts_map, stats))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _wait_and_purchase(
        self,
        item: DeferredPurchase,
        accounts_map: dict[int, AccountSnapshot],
        stats: AutobuyStats,
    ) -> None:
        operation = item.operation
        account = accounts_map.get(operation.account_id)
        if account is None:
            return
        now = self._clock()
        delay = (item.available_at - now).total_seconds()
        if delay > 0:
            wait_line = (
                f"autobuy:deferred_wait account_id={operation.account_id} "
                f"gift={operation.gift_id} seconds={delay:.2f}"
            )
            logger.info(wait_line)
            await asyncio.sleep(delay)
        try:
            balance = await self._telegram.fetch_balance(account)
        except Exception as exc:  # pragma: no cover - network failure branch
            logger.opt(exception=exc).debug(
                f"autobuy:deferred_balance_fail account_id={operation.account_id}"
            )
            balance = account.balance
        account.balance = balance
        if account.balance < operation.price:
            stats.record_reason(
                operation,
                reason="insufficient_account_balance_deferred",
                balance=account.balance,
                need=operation.price,
            )
            return
        try:
            await self._telegram.send_gift(operation, account)
            account.balance -= operation.price
            stats.record_purchase(operation, balance_after=account.balance, supply=operation.supply)
            logger.info(
                f"autobuy:deferred_done account_id={operation.account_id} gift={operation.gift_id}"
            )
        except Exception as exc:  # pragma: no cover - network failure branch
            reason = {"code": type(exc).__name__, "message": str(exc)[:400]}
            stats.record_failure(operation, reason="send_gift_failed", rpc=reason)
            fail_line = (
                f"autobuy:deferred_send_fail account_id={operation.account_id} "
                f"channel={operation.channel_id} gift={operation.gift_id} reason={reason}"
            )
            logger.opt(exception=exc).warning(fail_line)

    async def _send_reports(self, user_id: int, stats: dict, considered: Sequence[dict]) -> None:
        token = (self._settings.get_bot_token(user_id) or "").strip()
        if not token:
            logger.info(f"autobuy:report_skipped user_id={user_id} reason=no_token")
            return
        accounts = list(self._accounts.list_for_user(user_id))
        if not accounts:
            logger.info(f"autobuy:report_skipped user_id={user_id} reason=no_accounts")
            return
        chat_ids = await self._telegram.resolve_self_ids(accounts)
        if not chat_ids:
            logger.info(f"autobuy:report_skipped user_id={user_id} reason=no_dm_targets")
            return
        lines = self._report.build(stats, considered)
        messages = self._split_messages(lines)
        await self._notifications.send_reports(token, chat_ids, messages)

    @staticmethod
    def _split_messages(lines: Sequence[str], *, limit: int = 3800) -> list[str]:
        chunks: list[str] = []
        buffer: list[str] = []
        size = 0
        for line in lines:
            candidate = len(line) + 1
            if size + candidate > limit and buffer:
                chunks.append("\n".join(buffer))
                buffer = [line]
                size = len(line) + 1
            else:
                buffer.append(line)
                size += candidate
        if buffer:
            chunks.append("\n".join(buffer))
        return chunks
