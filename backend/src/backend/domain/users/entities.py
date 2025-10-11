"""Domain entities for user management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class User:
    """Aggregate root representing an authenticated operator."""

    id: int
    username: str
    password_hash: str
    created_at: datetime


@dataclass(slots=True, frozen=True)
class SessionToken:
    """Authentication session persisted for API access."""

    user_id: int
    token: str
    expires_at: datetime
