# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence

import httpx

from backend.application import NotificationPort, TelegramPort
from backend.domain import AccountSnapshot, PurchaseOperation
from backend.infrastructure.resilience import CircuitBreaker, resilient_call
from backend.services.tg_clients_service import get_stars_balance, tg_call
from backend.shared.config import load_config
from backend.shared.logging import logger

_config = load_config()


class TelegramRpcPort(TelegramPort):

    def __init__(self, *, balance_interval: float = 0.5, send_interval: float = 0.7):
        self._balance_interval = balance_interval
        self._send_interval = send_interval

    async def fetch_balance(self, account: AccountSnapshot) -> int:
        balance = await get_stars_balance(
            account.session_path,
            account.api_id,
            account.api_hash,
            min_interval=self._balance_interval,
        )
        return int(balance or 0)

    async def send_gift(self, operation: PurchaseOperation, account: AccountSnapshot) -> None:
        async def _call(client):
            return await client.send_gift(
                chat_id=int(operation.channel_id), gift_id=int(operation.gift_id)
            )

        await tg_call(
            account.session_path,
            account.api_id,
            account.api_hash,
            _call,
            min_interval=self._send_interval,
        )
        logger.info(
            f"autobuy:buy ok acc_id={account.id} chat_id={operation.channel_id} "
            f"gift_id={operation.gift_id}"
        )

    async def resolve_self_ids(self, accounts: Iterable[AccountSnapshot]) -> list[int]:
        resolved: set[int] = set()
        for account in accounts:
            try:
                me = await tg_call(
                    account.session_path,
                    account.api_id,
                    account.api_hash,
                    lambda client: client.get_me(),
                    min_interval=self._balance_interval,
                )
                value = int(getattr(me, "id", 0) or 0)
                if value > 0:
                    resolved.add(value)
            except Exception as exc:
                logger.opt(exception=exc).debug(f"autobuy:dm get_me fail acc_id={account.id}")
            await asyncio.sleep(0.05)
        return sorted(resolved)


class TelegramNotificationAdapter(NotificationPort):

    def __init__(self, *, timeout: float = 30.0, send_interval: float = 0.05):
        self._timeout = timeout
        self._interval = send_interval
        self._breaker = CircuitBreaker(
            failure_threshold=_config.resilience.circuit_fail_threshold,
            reset_timeout=_config.resilience.circuit_reset_timeout,
        )

    async def send_reports(
        self, token: str, chat_ids: Sequence[int], messages: Sequence[str]
    ) -> None:
        if not token or not chat_ids or not messages:
            return
        base = f"https://api.telegram.org/bot{token}"
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            for chat_id in chat_ids:
                for message in messages:
                    payload = {
                        "chat_id": int(chat_id),
                        "text": message,
                        "parse_mode": "HTML",
                    }
                    try:
                        response = await resilient_call(
                            http.post,
                            f"{base}/sendMessage",
                            json=payload,
                            breaker=self._breaker,
                            timeout=self._timeout,
                        )
                        if response.status_code != 200 or not response.json().get("ok"):
                            logger.warning(
                                f"autobuy:report send fail chat={chat_id} "
                                f"code={response.status_code} body={response.text[:200]}"
                            )
                    except Exception:
                        logger.exception(f"autobuy:report http fail chat={chat_id}")
                    await asyncio.sleep(self._interval)
