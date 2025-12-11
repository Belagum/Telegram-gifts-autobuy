# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.domain.users.exceptions import UserNotFoundError
from backend.domain.users.repositories import UserRepository
from backend.infrastructure.auth.login_attempts import clear_login_attempts
from backend.shared.logging import logger


class UnlockUserUseCase:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def execute(self, user_id: int) -> None:
        user = self._user_repo.find_by_id(user_id)

        if not user:
            raise UserNotFoundError()

        clear_login_attempts(user.username)

        logger.info(
            f"admin: Unlocked user account user_id={user_id} username={user.username}"
        )


__all__ = ["UnlockUserUseCase"]
