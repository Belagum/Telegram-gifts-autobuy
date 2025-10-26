# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import asyncio
from collections.abc import Sequence
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
from backend.shared.logging import logger

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
    forced_channel_fallback: bool = False


@dataclass(slots=True)
class AutobuyOutput:
    purchased: list[dict[str, Any]]
    skipped: int
    stats: dict[str, Any]
    deferred: list[dict[str, Any]]


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
        self._deferred: list[dict[str, Any]] = []
        self._deferred_keys: set[tuple[int, int]] = set()
        self.plan: PurchasePlan = PurchasePlan()

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

    def record_deferred(
        self,
        *,
        gift_id: int,
        account_id: int,
        channel_id: int,
        price: int,
        supply: int,
        locked_until: datetime,
    ) -> None:
        key = (gift_id, account_id)
        if key in self._deferred_keys:
            return
        self._deferred_keys.add(key)
        payload = {
            "gift_id": gift_id,
            "account_id": account_id,
            "channel_id": channel_id,
            "price": price,
            "supply": supply,
            "run_at": locked_until.isoformat().replace("+00:00", "Z"),
            "reason": "locked_until",
        }
        self._deferred.append(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channels": self._channels,
            "accounts": self._accounts,
            "global_skips": self._global_skips,
            "plan_skips": self._plan_skips,
            "plan": [asdict(op) for op in self.plan],
            "deferred": [dict(row) for row in self._deferred],
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

    def __init__(self, selector: ChannelSelector, stats: AutobuyStats):
        self._selector = selector
        self._stats = stats

    def plan(
        self,
        *,
        accounts: Sequence[AccountSnapshot],
        gifts: Sequence[GiftPayload],
        stars: dict[int, int],
        forced_channel_id: int | None = None,
        forced_channel_fallback: bool = False,
    ) -> PurchasePlan:
        remain_by_gift: dict[int, int] = {
            p.candidate.gift_id: p.candidate.available_amount for p in gifts
        }
        already_by_account: dict[tuple[int, int], int] = {}
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
                selector_forced_id = None if forced_channel_fallback else forced_channel_id
                channel = self._selector.best_for(candidate, selector_forced_id)
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
                locked_until = self._resolve_lock(payload.raw, account.id)
                if locked_until and locked_until > datetime.now(UTC):
                    self._stats.record_deferred(
                        gift_id=gift_id,
                        account_id=account.id,
                        channel_id=target_channel_id,
                        price=price,
                        supply=candidate.total_supply,
                        locked_until=locked_until,
                    )
                    continue
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
        return self._stats.plan

    @staticmethod
    def _resolve_lock(payload: dict[str, Any], account_id: int) -> datetime | None:
        locks = payload.get("locks") or {}
        raw = locks.get(str(account_id)) if isinstance(locks, dict) else None
        if raw is None and isinstance(locks, dict):
            raw = locks.get(account_id)
        if raw is None:
            return None
        if isinstance(raw, int | float):
            return datetime.fromtimestamp(float(raw), tz=UTC)
        if isinstance(raw, str):
            cleaned = raw.strip()
            if not cleaned:
                return None
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(cleaned)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return None


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
    DEFERRED = "⏳"

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
        deferred = stats.get("deferred") or []
        if deferred:
            lines.append("")
            lines.append(f"{self.DEFERRED} Отложенные покупки:")
            for row in deferred:
                gift_id = row.get("gift_id")
                account_id = row.get("account_id")
                channel_id = row.get("channel_id")
                price_val = row.get("price")
                run_at = row.get("run_at")
                price_txt = price_val if price_val is not None else "?"
                lines.append(
                    f"• gift={gift_id} acc={account_id} ch={channel_id} {price_txt}{self.STAR} "
                    f"→ будет куплен после {run_at}, так как лок действует до этого времени"
                )
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
    ) -> None:
        self._accounts = accounts
        self._channels = channels
        self._telegram = telegram
        self._notifications = notifications
        self._settings = settings
        self._validator = GiftValidator()
        self._report = ReportBuilder()

    async def execute_with_user_check(self, user_id: int, gifts: list[dict]) -> AutobuyOutput:
        from backend.infrastructure.db import SessionLocal
        from backend.infrastructure.db.models import User, UserSettings

        session = SessionLocal()
        try:
            user = session.get(User, user_id)
            if not user or not bool(getattr(user, "gifts_autorefresh", False)):
                logger.info(f"autobuy:skip user_id={user_id} reason=autorefresh_off")
                return AutobuyOutput(
                    purchased=[],
                    skipped=len(gifts or []),
                    stats={
                        "channels": {},
                        "accounts": {},
                        "global_skips": [{"reason": "autorefresh_off"}],
                        "plan_skips": [],
                        "plan": [],
                    },
                    deferred=[],
                )

            settings = session.get(UserSettings, user_id)
            forced_channel_id = None
            if settings and settings.buy_target_id is not None:
                forced_channel_id = int(settings.buy_target_id)
            forced_channel_fallback = (
                bool(getattr(settings, "buy_target_on_fail_only", False)) if settings else False
            )
            if forced_channel_id is None:
                forced_channel_fallback = False
        finally:
            session.close()

        data = AutobuyInput(
            user_id=user_id,
            gifts=list(gifts or []),
            forced_channel_id=forced_channel_id,
            forced_channel_fallback=forced_channel_fallback,
        )
        return await self.execute(data)

    async def execute(self, data: AutobuyInput) -> AutobuyOutput:
        logger.bind(user_id=data.user_id).info(f"autobuy:start gifts={len(data.gifts)}")
        gifts, skipped_rows = self._validator.validate_many(data.gifts)
        accounts = list(self._accounts.list_for_user(data.user_id))
        if not accounts:
            logger.info(f"autobuy:no_accounts user_id={data.user_id}")
            early_stats = self._empty_stats(skipped_rows)
            early_stats["global_skips"].append({"reason": "no_accounts"})
            return AutobuyOutput(
                purchased=[], skipped=len(data.gifts), stats=early_stats, deferred=[]
            )
        channels = list(self._channels.list_for_user(data.user_id))
        if data.forced_channel_id is None and not channels:
            logger.info(f"autobuy:no_channels user_id={data.user_id}")
            early_stats = self._empty_stats(skipped_rows)
            early_stats["global_skips"].append({"reason": "no_channels"})
            return AutobuyOutput(
                purchased=[], skipped=len(data.gifts), stats=early_stats, deferred=[]
            )
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
        planner = PurchasePlanner(selector, stats)
        plan = planner.plan(
            accounts=enriched_accounts,
            gifts=gifts,
            stars=stars,
            forced_channel_id=data.forced_channel_id,
            forced_channel_fallback=data.forced_channel_fallback,
        )
        await self._execute_plan(plan, enriched_accounts, stats)
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
        deferred = list(stats_dict.get("deferred") or [])
        await self._send_reports(data.user_id, stats_dict, list(data.gifts))
        logger.bind(user_id=data.user_id).info(
            f"autobuy:summary purchased={len(purchased)} skipped={skipped} plan={len(plan)} "
            f"deferred={len(deferred)}"
        )
        return AutobuyOutput(
            purchased=purchased, skipped=skipped, stats=stats_dict, deferred=deferred
        )

    @staticmethod
    def _empty_stats(skipped_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
        return {
            "channels": {},
            "accounts": {},
            "global_skips": [dict(row) for row in skipped_rows],
            "plan_skips": [],
            "plan": [],
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
                reason = {"code": type(exc).__name__}
                stats.record_failure(op, reason="send_gift_failed", rpc=reason)
                logger.opt(exception=exc).warning(
                    f"autobuy:send_fail account_id={op.account_id} channel={op.channel_id} "
                    f"gift={op.gift_id} reason={reason}"
                )
            await asyncio.sleep(0)

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
