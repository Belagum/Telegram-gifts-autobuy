# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Compatibility layer exposing legacy autobuy API."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.application.use_cases.autobuy import AutobuyInput
from backend.container import container
from backend.db import SessionLocal
from backend.logger import logger
from backend.models import User, UserSettings


def _legacy_skip(reason: str, gifts: list[dict]) -> dict:
    return {
        "purchased": [],
        "skipped": len(gifts or []),
        "stats": {
            "channels": {},
            "accounts": {},
            "global_skips": [{"reason": reason}],
            "plan_skips": [],
            "plan": [],
        },
    }


async def autobuy_new_gifts(user_id: int, gifts: list[dict]) -> dict:
    """Entry point used by background workers."""

    session: Session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user or not bool(getattr(user, "gifts_autorefresh", False)):
            logger.info(f"autobuy:skip user_id={user_id} reason=autorefresh_off")
            return _legacy_skip("autorefresh_off", gifts)
        settings = session.get(UserSettings, user_id)
        forced_channel_id = (
            int(settings.buy_target_id) if settings and settings.buy_target_id is not None else None
        )
    finally:
        session.close()

    use_case = container.autobuy_use_case
    output = await use_case.execute(
        AutobuyInput(
            user_id=user_id,
            gifts=list(gifts or []),
            forced_channel_id=forced_channel_id,
        )
    )
    return {
        "purchased": output.purchased,
        "skipped": output.skipped,
        "stats": output.stats,
        "deferred": output.deferred,
    }
