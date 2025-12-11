# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from sqlalchemy import text

from backend.infrastructure.db import ENGINE


def check_database() -> bool:
    with ENGINE.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


__all__ = ["check_database"]
