# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from flask import Request, jsonify, request

from backend.shared.config import load_config


@dataclass
class Bucket:
    timestamps: deque[float]


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self._limit = max(1, int(limit))
        self._window = max(0.1, float(window_seconds))
        self._buckets: dict[str, Bucket] = defaultdict(lambda: Bucket(deque(maxlen=self._limit)))

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self._buckets[key]
        # Drop old
        while bucket.timestamps and (now - bucket.timestamps[0]) > self._window:
            bucket.timestamps.popleft()
        if len(bucket.timestamps) >= self._limit:
            return False
        bucket.timestamps.append(now)
        return True


def _client_key(req: Request) -> str:
    forwarded = req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return forwarded or (req.remote_addr or "unknown")


def rate_limit(limit: int | None = None, window_seconds: float | None = None):
    config = load_config()
    enabled = config.security.enable_rate_limit
    limiter = InMemoryRateLimiter(
        limit or config.security.rate_limit_requests,
        window_seconds or config.security.rate_limit_window,
    )

    def decorator(f: Callable):
        if not enabled:
            return f

        def wrapper(*args, **kwargs):
            key = f"{request.path}:{_client_key(request)}"
            if not limiter.allow(key):
                return jsonify({"error": "rate_limited"}), 429
            return f(*args, **kwargs)

        # Preserve attributes for Flask
        wrapper.__name__ = getattr(f, "__name__", "wrapped")
        wrapper.__doc__ = f.__doc__
        return wrapper

    return decorator


__all__ = ["rate_limit"]
