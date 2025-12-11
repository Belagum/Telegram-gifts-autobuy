# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class AuditLogEntry:
    id: int
    timestamp: datetime
    action: str
    user_id: int | None
    ip_address: str | None
    success: bool
    details: dict[str, Any]


@dataclass
class UserInfo:
    id: int
    username: str
    is_admin: bool
    created_at: datetime | None
    last_login: datetime | None
    is_locked: bool
    failed_attempts: int


@dataclass
class SuspiciousActivity:
    severity: str
    activity_type: str
    description: str
    user_id: int | None
    username: str | None
    ip_address: str | None
    count: int
    first_seen: datetime
    last_seen: datetime
    details: dict[str, Any]


@dataclass
class ErrorStats:
    ip_address: str | None
    error_count: int
    unique_actions: int
    first_error: datetime
    last_error: datetime
    sample_errors: list[str]


class AuditLogRepository(ABC):
    @abstractmethod
    def list_logs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        action: str | None = None,
        user_id: int | None = None,
        ip_address: str | None = None,
        success: bool | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[AuditLogEntry], int]:
        pass

    @abstractmethod
    def get_by_user(self, user_id: int, limit: int = 100) -> list[AuditLogEntry]:
        pass

    @abstractmethod
    def get_by_action(self, action: str, limit: int = 100) -> list[AuditLogEntry]:
        pass

    @abstractmethod
    def get_all_actions(self) -> list[str]:
        pass


class AdminRepository(ABC):
    @abstractmethod
    def get_suspicious_activities(self, limit: int = 50) -> list[SuspiciousActivity]:
        pass

    @abstractmethod
    def get_error_stats(self, limit: int = 50) -> list[ErrorStats]:
        pass

    @abstractmethod
    def list_users(self) -> list[UserInfo]:
        pass

    @abstractmethod
    def get_dashboard_stats(self) -> dict[str, Any]:
        pass


__all__ = [
    "AuditLogEntry",
    "UserInfo",
    "SuspiciousActivity",
    "ErrorStats",
    "AuditLogRepository",
    "AdminRepository",
]
