# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.domain.admin.repositories import AuditLogEntry, AuditLogRepository


class GetUserAuditUseCase:
    def __init__(self, audit_log_repo: AuditLogRepository) -> None:
        self._repo = audit_log_repo
    
    def execute(self, user_id: int, limit: int = 100) -> list[AuditLogEntry]:
        return self._repo.get_by_user(user_id, limit=limit)


__all__ = ["GetUserAuditUseCase"]

