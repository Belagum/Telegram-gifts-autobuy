# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any


def merge_new(prev: list[dict], cur: list[dict]) -> list[dict]:
    by_id: dict[int, dict] = {int(x["id"]): dict(x) for x in prev}
    for raw in cur:
        gift_id = int(raw["id"])
        candidate = dict(raw)
        locks = {str(k): v for k, v in (candidate.get("locks") or {}).items()}
        existing = by_id.get(gift_id)
        if existing:
            merged = {**existing, **candidate}
            merged_locks = {str(k): v for k, v in (existing.get("locks") or {}).items()}
            merged_locks.update(locks)
            if merged_locks:
                merged["locks"] = merged_locks
                merged["locked_until_date"] = _earliest_lock(
                    merged_locks, merged.get("locked_until_date")
                )
            else:
                merged.pop("locks", None)
                merged.pop("locked_until_date", None)
            by_id[gift_id] = merged
        else:
            if locks:
                candidate["locks"] = locks
                candidate["locked_until_date"] = _earliest_lock(
                    locks, candidate.get("locked_until_date")
                )
            else:
                candidate.pop("locks", None)
            by_id[gift_id] = candidate
    return sorted(by_id.values(), key=lambda x: (x.get("price", 0), x["id"]))


def _earliest_lock(locks: dict[str, Any], fallback: Any) -> str | None:
    best: datetime | None = None
    for value in locks.values():
        dt = _parse_lock(value)
        if dt is None:
            continue
        if best is None or dt < best:
            best = dt
    if best is None:
        return fallback if isinstance(fallback, str) else None
    return best.isoformat().replace("+00:00", "Z")


def _parse_lock(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def hash_items(items: list[dict[str, Any]]) -> str:
    m = hashlib.md5()
    for it in items:
        m.update(
            str(
                (
                    it.get("id"),
                    it.get("price"),
                    it.get("is_limited"),
                    it.get("available_amount"),
                    it.get("limited_per_user"),
                    it.get("per_user_remains"),
                    it.get("per_user_available"),
                    it.get("require_premium"),
                    it.get("locked_until_date"),
                    it.get("sticker_file_id"),
                    it.get("sticker_mime"),
                    tuple(
                        sorted(
                            (str(k), "" if v is None else str(v))
                            for k, v in (it.get("locks") or {}).items()
                        )
                    ),
                )
            ).encode("utf-8")
        )
    return m.hexdigest()
