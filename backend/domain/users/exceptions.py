# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.shared.errors.base import DomainError


class UserAlreadyExistsError(DomainError):
    code = "user_already_exists"
    message = "User with provided username already exists."


class InvalidCredentialsError(DomainError):
    code = "invalid_credentials"
    message = "Invalid username or password provided."
