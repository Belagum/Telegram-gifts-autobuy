# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogsFilterDTO(BaseModel):
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    action: str | None = None
    user_id: int | None = None
    ip_address: str | None = None
    success: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    
    model_config = ConfigDict(from_attributes=True)


class AuditLogDTO(BaseModel):
    id: int
    timestamp: datetime
    action: str
    user_id: int | None
    ip_address: str | None
    success: bool
    details: dict[str, Any]
    
    model_config = ConfigDict(from_attributes=True)


class AuditLogListDTO(BaseModel):
    logs: list[AuditLogDTO]
    total: int
    limit: int
    offset: int
    
    model_config = ConfigDict(from_attributes=True)


class SuspiciousActivityDTO(BaseModel):
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
    
    model_config = ConfigDict(from_attributes=True)


class ErrorStatsDTO(BaseModel):
    ip_address: str | None
    error_count: int
    unique_actions: int
    first_error: datetime
    last_error: datetime
    sample_errors: list[str]
    
    model_config = ConfigDict(from_attributes=True)


class UserInfoDTO(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: datetime | None
    last_login: datetime | None
    is_locked: bool
    failed_attempts: int
    
    model_config = ConfigDict(from_attributes=True)


class DashboardStatsDTO(BaseModel):
    total_users: int
    total_logs: int
    logs_last_24h: int
    failed_logins_24h: int
    successful_logins_24h: int
    active_sessions: int
    errors_last_7d: int
    most_active_users: list[dict[str, Any]]
    
    model_config = ConfigDict(from_attributes=True)


class ActionCategoriesDTO(BaseModel):
    actions: list[str]
    
    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "AuditLogsFilterDTO",
    "AuditLogDTO",
    "AuditLogListDTO",
    "SuspiciousActivityDTO",
    "ErrorStatsDTO",
    "UserInfoDTO",
    "DashboardStatsDTO",
    "ActionCategoriesDTO",
]

