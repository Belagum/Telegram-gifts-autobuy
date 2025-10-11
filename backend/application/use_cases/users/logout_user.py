"""Use-case for revoking access tokens."""

from __future__ import annotations

from backend.domain.users.repositories import SessionTokenRepository


class LogoutUserUseCase:
    def __init__(self, *, tokens: SessionTokenRepository) -> None:
        self._tokens = tokens

    def execute(self, token: str) -> None:
        if token:
            self._tokens.revoke(token)
