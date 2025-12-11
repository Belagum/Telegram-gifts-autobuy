# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from datetime import datetime

from backend.domain.admin.repositories import AuditLogEntry, AuditLogRepository


class GetAuditLogsUseCase:
    def __init__(self, audit_log_repo: AuditLogRepository) -> None:
        self._repo = audit_log_repo

    def execute(
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
        return self._repo.list_logs(
            limit=limit,
            offset=offset,
            action=action,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            start_date=start_date,
            end_date=end_date,
        )

    def get_all_actions(self) -> list[str]:
        return self._repo.get_all_actions()


__all__ = ["GetAuditLogsUseCase"]
