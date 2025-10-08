# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""In-memory resilient queue implementation."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from backend.logger import logger


@dataclass(slots=True)
class QueueMessage[T]:
    """Message wrapper with idempotency token."""

    payload: T
    message_id: str
    inserted_at: float


class ResilientQueue[T]:
    """Queue with visibility timeout to emulate external brokers."""

    def __init__(self, max_size: int, visibility_timeout: float) -> None:
        self._queue: asyncio.Queue[QueueMessage[T]] = asyncio.Queue(maxsize=max_size)
        self._visibility_timeout = visibility_timeout
        self._inflight: dict[str, tuple[QueueMessage[T], float]] = {}

    async def put(self, message: QueueMessage[T]) -> None:
        await self._queue.put(message)
        logger.debug(f"queue: put message_id={message.message_id}")

    async def get(self) -> QueueMessage[T]:
        message = await self._queue.get()
        self._inflight[message.message_id] = (message, time.monotonic())
        logger.debug(f"queue: get message_id={message.message_id}")
        return message

    async def ack(self, message_id: str) -> None:
        self._inflight.pop(message_id, None)
        logger.debug(f"queue: ack message_id={message_id}")

    async def requeue_expired(self) -> None:
        now = time.monotonic()
        expired = [
            message_id
            for message_id, (_message, ts) in self._inflight.items()
            if now - ts >= self._visibility_timeout
        ]
        for message_id in expired:
            message, _ = self._inflight.pop(message_id)
            await self._queue.put(message)
            logger.warning(f"queue: message requeued message_id={message_id}")


__all__ = ["QueueMessage", "ResilientQueue"]
