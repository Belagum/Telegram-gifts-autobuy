# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.domain.admin.repositories import AdminRepository, ErrorStats


class GetErrorStatsUseCase:
    def __init__(self, admin_repo: AdminRepository) -> None:
        self._repo = admin_repo
    
    def execute(self, limit: int = 50) -> list[ErrorStats]:
        return self._repo.get_error_stats(limit=limit)


__all__ = ["GetErrorStatsUseCase"]

