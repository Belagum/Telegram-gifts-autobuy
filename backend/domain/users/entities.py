# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class User:

    id: int
    username: str
    password_hash: str
    created_at: datetime


@dataclass(slots=True, frozen=True)
class SessionToken:

    user_id: int
    token: str
    expires_at: datetime
