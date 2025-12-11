# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import ClassVar

from backend.shared.logging import logger


@dataclass
class LoginAttempt:
    timestamp: float
    success: bool
    ip_address: str | None = None


class LoginAttemptsTracker:
    MAX_ATTEMPTS: ClassVar[int] = 5
    LOCKOUT_DURATION: ClassVar[float] = 15 * 60  # 15 minutes in seconds
    ATTEMPT_WINDOW: ClassVar[float] = 60 * 60  # 1 hour in seconds

    def __init__(self) -> None:
        self._attempts: dict[str, deque[LoginAttempt]] = defaultdict(
            lambda: deque(maxlen=self.MAX_ATTEMPTS * 2)
        )
        self._lock = Lock()
        self._lockouts: dict[str, float] = {}  # username -> unlock_time

    def record_attempt(
        self, username: str, success: bool, ip_address: str | None = None
    ) -> None:
        with self._lock:
            attempt = LoginAttempt(
                timestamp=time.time(),
                success=success,
                ip_address=ip_address,
            )

            self._attempts[username].append(attempt)

            if success and username in self._lockouts:
                del self._lockouts[username]
                logger.info(f"login_attempts: cleared lockout for user={username}")
            elif not success:
                self._check_and_lock(username)

    def is_locked(self, username: str) -> bool:
        with self._lock:
            if username not in self._lockouts:
                return False

            unlock_time = self._lockouts[username]
            now = time.time()

            if now >= unlock_time:
                del self._lockouts[username]
                logger.info(f"login_attempts: lockout expired for user={username}")
                return False

            return True

    def get_lockout_remaining(self, username: str) -> float:
        with self._lock:
            if username not in self._lockouts:
                return 0.0

            now = time.time()
            remaining = max(0.0, self._lockouts[username] - now)
            return remaining

    def get_failed_attempts_count(self, username: str) -> int:
        with self._lock:
            if username not in self._attempts:
                return 0

            now = time.time()
            cutoff = now - self.ATTEMPT_WINDOW

            failed_count = sum(
                1
                for attempt in self._attempts[username]
                if not attempt.success and attempt.timestamp > cutoff
            )

            return failed_count

    def clear_attempts(self, username: str) -> None:
        with self._lock:
            if username in self._attempts:
                del self._attempts[username]
            if username in self._lockouts:
                del self._lockouts[username]
            logger.info(f"login_attempts: cleared all attempts for user={username}")

    def _check_and_lock(self, username: str) -> None:
        now = time.time()
        cutoff = now - self.ATTEMPT_WINDOW

        failed_attempts = [
            attempt
            for attempt in self._attempts[username]
            if not attempt.success and attempt.timestamp > cutoff
        ]

        if len(failed_attempts) >= self.MAX_ATTEMPTS:
            unlock_time = now + self.LOCKOUT_DURATION
            self._lockouts[username] = unlock_time

            ips = {
                attempt.ip_address for attempt in failed_attempts if attempt.ip_address
            }
            logger.warning(
                f"login_attempts: ACCOUNT LOCKED user={username} "
                f"failed_attempts={len(failed_attempts)} "
                f"lockout_duration={self.LOCKOUT_DURATION}s "
                f"ip_addresses={list(ips) if ips else 'unknown'}"
            )

    def get_stats(self, username: str) -> dict:
        with self._lock:
            failed_count = self.get_failed_attempts_count(username)
            is_locked = self.is_locked(username)
            remaining = self.get_lockout_remaining(username) if is_locked else 0.0

            return {
                "username": username,
                "failed_attempts": failed_count,
                "is_locked": is_locked,
                "lockout_remaining_seconds": round(remaining, 1),
                "max_attempts": self.MAX_ATTEMPTS,
                "attempts_window_seconds": self.ATTEMPT_WINDOW,
            }


_tracker = LoginAttemptsTracker()


def record_login_attempt(
    username: str, success: bool, ip_address: str | None = None
) -> None:
    _tracker.record_attempt(username, success, ip_address)


def is_account_locked(username: str) -> bool:
    return _tracker.is_locked(username)


def get_lockout_remaining(username: str) -> float:
    return _tracker.get_lockout_remaining(username)


def get_login_stats(username: str) -> dict:
    return _tracker.get_stats(username)


def clear_login_attempts(username: str) -> None:
    _tracker.clear_attempts(username)


__all__ = [
    "LoginAttemptsTracker",
    "record_login_attempt",
    "is_account_locked",
    "get_lockout_remaining",
    "get_login_stats",
    "clear_login_attempts",
]
