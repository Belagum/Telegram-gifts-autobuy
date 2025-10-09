# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Resilience utilities (timeouts, retries, circuit breaker)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from backend.config import load_config
from backend.logger import logger
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_config = load_config()
T = TypeVar("T")


@dataclass
class CircuitBreaker:
    """Simple in-memory circuit breaker."""

    failure_threshold: int
    reset_timeout: float

    def __post_init__(self) -> None:
        self._failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.reset_timeout:
            logger.info("breaker: half-open state")
            self._opened_at = None
            self._failures = 0
            return True
        logger.warning("breaker: open state refusing call")
        return False

    def on_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()
            logger.error("breaker: opening circuit after failures")


async def resilient_call(  # noqa: UP047
    func: Callable[..., Awaitable[T]],
    *args: Any,
    breaker: CircuitBreaker | None = None,
    timeout: float | None = None,
    **kwargs: Any,
) -> T:
    """Execute call with retries, timeout, and optional circuit breaker."""

    breaker = breaker or CircuitBreaker(
        failure_threshold=_config.resilience.circuit_fail_threshold,
        reset_timeout=_config.resilience.circuit_reset_timeout,
    )

    if not breaker.allow():
        msg = "Circuit breaker is open"
        raise RuntimeError(msg)

    timeout = timeout or _config.resilience.default_timeout

    retry = AsyncRetrying(
        stop=stop_after_attempt(_config.resilience.max_retries + 1),
        wait=wait_exponential(
            multiplier=_config.resilience.backoff_base,
            max=_config.resilience.backoff_cap,
        ),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )

    try:
        async for attempt in retry:
            with attempt:
                logger.debug(
                    f"resilience: attempt={attempt.retry_state.attempt_number} func={func.__name__}"
                )
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                breaker.on_success()
                return result
    except RetryError as exc:
        breaker.on_failure()
        last_exc = exc.last_attempt.exception()
        if last_exc is None:
            raise RuntimeError("resilience: retry failed without exception") from exc
        raise last_exc from exc
    except Exception:
        breaker.on_failure()
        raise
    else:
        raise RuntimeError("resilience: reached unexpected branch")


__all__ = ["CircuitBreaker", "resilient_call"]
