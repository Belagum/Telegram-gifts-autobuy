# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from typing import Any

from backend.domain.admin.repositories import AdminRepository


class GetDashboardStatsUseCase:
    def __init__(self, admin_repo: AdminRepository) -> None:
        self._repo = admin_repo

    def execute(self) -> dict[str, Any]:
        return self._repo.get_dashboard_stats()


__all__ = ["GetDashboardStatsUseCase"]
