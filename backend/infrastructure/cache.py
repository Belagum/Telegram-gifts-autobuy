# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Simple in-memory cache layer with TTL semantics."""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from threading import Lock

from backend.logger import logger


@dataclass(slots=True)
class CacheEntry[V]:
    """Single cache entry."""

    value: V
    expires_at: float

    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class InMemoryTTLCache[K: Hashable, V]:
    """Thread-safe cache with TTL and lazy refresh support."""

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
