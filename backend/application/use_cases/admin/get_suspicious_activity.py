# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.domain.admin.repositories import (AdminRepository,
                                               SuspiciousActivity)


class GetSuspiciousActivityUseCase:
    def __init__(self, admin_repo: AdminRepository) -> None:
        self._repo = admin_repo

    def execute(self, limit: int = 50) -> list[SuspiciousActivity]:
        return self._repo.get_suspicious_activities(limit=limit)


__all__ = ["GetSuspiciousActivityUseCase"]
