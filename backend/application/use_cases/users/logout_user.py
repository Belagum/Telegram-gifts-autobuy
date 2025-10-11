# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.domain.users.repositories import SessionTokenRepository


class LogoutUserUseCase:
    def __init__(self, *, tokens: SessionTokenRepository) -> None:
        self._tokens = tokens

    def execute(self, token: str) -> None:
        if token:
            self._tokens.revoke(token)
