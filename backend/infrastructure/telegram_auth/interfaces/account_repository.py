# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from typing import Protocol

from backend.infrastructure.telegram_auth.models.dto import (
    AccountData,
    ApiCredentials,
)


class IAccountRepository(Protocol):
    def get_api_credentials(self, user_id: int, api_profile_id: int) -> ApiCredentials | None: ...

    def save_account(
        self,
        user_id: int,
        api_profile_id: int,
        phone: str,
        session_path: str,
        account_data: AccountData
    ) -> None: ...

