# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.domain.admin.repositories import AdminRepository, UserInfo


class ListUsersUseCase:
    def __init__(self, admin_repo: AdminRepository) -> None:
        self._repo = admin_repo

    def execute(self) -> list[UserInfo]:
        return self._repo.list_users()


__all__ = ["ListUsersUseCase"]
