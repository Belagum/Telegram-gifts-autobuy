# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from backend.shared.errors.base import DomainError


class UserAlreadyExistsError(DomainError):
    code = "user_already_exists"


class InvalidCredentialsError(DomainError):
    code = "invalid_credentials"
