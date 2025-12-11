# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from typing import Protocol

from backend.infrastructure.telegram_auth.models.dto import LoginResult


class ILoginManager(Protocol):
    def start_login(
        self, user_id: int, api_profile_id: int, phone: str
    ) -> LoginResult: ...

    def confirm_code(self, login_id: str, code: str) -> LoginResult: ...

    def confirm_password(self, login_id: str, password: str) -> LoginResult: ...

    def cancel(self, login_id: str) -> LoginResult: ...
