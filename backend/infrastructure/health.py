# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Health and readiness checks."""

from __future__ import annotations

from backend.db import ENGINE
from sqlalchemy import text


def check_database() -> bool:
    """Check database connectivity."""

    with ENGINE.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


__all__ = ["check_database"]
