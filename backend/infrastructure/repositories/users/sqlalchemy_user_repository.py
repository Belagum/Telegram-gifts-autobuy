# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from backend.domain.users.entities import SessionToken as DomainSessionToken
from backend.domain.users.entities import User as DomainUser
from backend.domain.users.repositories import SessionTokenRepository, UserRepository
from backend.infrastructure.db.models import SessionToken, User
from backend.infrastructure.db.session import session_scope


class SqlAlchemyUserRepository(UserRepository):
    def find_by_username(self, username: str) -> DomainUser | None:
        with session_scope() as session:
            row = session.query(User).filter(User.username == username).first()
            if not row:
                return None
            return DomainUser(
                id=row.id,
                username=row.username,
                password_hash=row.password_hash,
                created_at=datetime.now(UTC),
            )

    def find_by_id(self, user_id: int) -> DomainUser | None:
        with session_scope() as session:
            row = session.query(User).filter(User.id == user_id).first()
            if not row:
                return None
            return DomainUser(
                id=row.id,
                username=row.username,
                password_hash=row.password_hash,
                created_at=datetime.now(UTC),
            )

    def add(self, user: DomainUser) -> DomainUser:
        with session_scope() as session:
            row = User(username=user.username, password_hash=user.password_hash)
            session.add(row)
            session.flush() 
            session.refresh(row)
            return DomainUser(
                id=row.id,
                username=row.username,
                password_hash=row.password_hash,
                created_at=datetime.now(UTC),
            )


class SqlAlchemySessionTokenRepository(SessionTokenRepository):
    def replace_for_user(self, user_id: int) -> DomainSessionToken:
        with session_scope() as session:
            session.query(SessionToken).filter(SessionToken.user_id == user_id).delete()
            token_value = secrets.token_urlsafe(48)
            expires_at = datetime.now(UTC) + timedelta(days=7)
            row = SessionToken(user_id=user_id, token=token_value, expires_at=expires_at)
            session.add(row)
            return DomainSessionToken(user_id=user_id, token=token_value, expires_at=expires_at)

    def revoke(self, token: str) -> None:
        with session_scope() as session:
            session.query(SessionToken).filter(SessionToken.token == token).delete()
