"""Password hashing strategies."""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

from backend.domain.users.repositories import PasswordHasher


class WerkzeugPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return str(generate_password_hash(password))

    def verify(self, password: str, hashed: str) -> bool:
        return bool(check_password_hash(hashed, password))
