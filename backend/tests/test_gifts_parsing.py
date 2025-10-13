# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from backend.services.gifts_service import _normalize_gift


def _gift_stub(**kwargs):
    return SimpleNamespace(**kwargs)


def test_normalize_limited_gift_minimizes_per_user_available():
    locked_dt = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    raw = _gift_stub(
        limited_per_user=True,
        per_user_remains="7",
        require_premium=True,
        total_amount=123,
        locked_until=None,
        locked_until_date=None,
    )
    sticker = _gift_stub(file_id="file", file_unique_id="uniq", mime_type="video/webm")
    gift = _gift_stub(
        id="456",
        price="15",
        is_limited=True,
        available_amount="20",
        total_amount=None,
        locked_until=locked_dt,
        locked_until_date=None,
        raw=raw,
        sticker=sticker,
    )

    normalized = _normalize_gift(gift)

    assert normalized["id"] == 456
    assert normalized["price"] == 15
    assert normalized["available_amount"] == 20
    assert normalized["per_user_remains"] == 7
    assert normalized["per_user_available"] == 7
    assert normalized["require_premium"] is True
    assert normalized["total_amount"] == 123
    assert normalized["locked_until_date"] == "2025-01-02T03:04:05Z"
    assert normalized["sticker_file_id"] == "file"
    assert normalized["sticker_unique_id"] == "uniq"
    assert normalized["sticker_mime"] == "video/webm"


def test_normalize_unlimited_gift_preserves_defaults():
    raw = _gift_stub(
        limited_per_user=False,
        per_user_remains=5,
        require_premium=False,
        locked_until_date="",
    )
    gift = _gift_stub(
        id=789,
        price=None,
        is_limited=False,
        available_amount="99",
        raw=raw,
        sticker=None,
    )

    normalized = _normalize_gift(gift)

    assert normalized["id"] == 789
    assert normalized["price"] == 0
    assert normalized["is_limited"] is False
    assert normalized["available_amount"] is None
    assert normalized["per_user_remains"] is None
    assert normalized["per_user_available"] is None
    assert normalized["locked_until_date"] is None
