# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar

from backend.shared.logging import logger

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(slots=True)
class CacheEntry(Generic[V]):  # noqa: UP046
    value: V
    expires_at: float

    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class InMemoryTTLCache(Generic[K, V]):  # noqa: UP046
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._store: dict[K, CacheEntry[V]] = {}

    def get_or_set(self, key: K, factory: Callable[[], V]) -> V:
        with self._lock:
            entry = self._store.get(key)
            if entry and not entry.is_expired():
                logger.debug(f"cache: hit key={key}")
                return entry.value

        logger.debug(f"cache: miss key={key}")
        value = factory()
        expires_at = time.monotonic() + self._ttl
        with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=expires_at)
        return value

    def invalidate(self, key: K) -> None:
        with self._lock:
            if key in self._store:
                logger.debug(f"cache: invalidate key={key}")
                self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            logger.debug("cache: clear all keys")
            self._store.clear()


__all__ = ["InMemoryTTLCache"]
