"""User specific domain exceptions."""

from __future__ import annotations

from backend.shared.errors.base import DomainError


class UserAlreadyExistsError(DomainError):
    code = "user_already_exists"
    message = "User with provided username already exists."


class InvalidCredentialsError(DomainError):
    code = "invalid_credentials"
    message = "Invalid username or password provided."
