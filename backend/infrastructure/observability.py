# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import contextmanager

from prometheus_client import Counter, Gauge, Histogram

from backend.shared.config import load_config

_config = load_config()

REQUEST_LATENCY = Histogram(
    "giftbuyer_request_latency_seconds",
    "Request latency",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
REQUEST_COUNTER = Counter(
    "giftbuyer_requests_total",
    "Number of processed requests",
    labelnames=("endpoint", "status"),
)
WORKER_GAUGE = Gauge("giftbuyer_workers", "Active background workers")


@contextmanager
def track_latency(endpoint: str, status_getter: Callable[[], str]):
    if not _config.observability.metrics_enabled:
        yield
        return

    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        REQUEST_LATENCY.observe(duration)
        REQUEST_COUNTER.labels(endpoint=endpoint, status=status_getter()).inc()


__all__ = [
    "REQUEST_COUNTER",
    "REQUEST_LATENCY",
    "WORKER_GAUGE",
    "track_latency",
]
