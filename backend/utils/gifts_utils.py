# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any


def _normalise_locks(raw: Any) -> dict[int, str]:
    if not isinstance(raw, dict):
        return {}
    locks: dict[int, str] = {}
    for key, value in raw.items():
        try:
            account_id = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, str):
            text = value.strip()
            if text:
                locks[account_id] = text
        elif isinstance(value, (int | float)):
            ts = int(value)
            if ts > 0:
                locks[account_id] = (
                    datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")
                )
    return locks


def _is_int_key(value: Any) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def _inactive_lock_ids(raw: Any) -> set[int]:
    if not isinstance(raw, dict):
        return set()
    inactive: set[int] = set()
    for key, value in raw.items():
        try:
            account_id = int(key)
        except (TypeError, ValueError):
            continue
        if value in (None, "", 0):
            inactive.add(account_id)
    return inactive


def _merge_locks(existing: dict[int, str], incoming: dict[int, str]) -> dict[int, str]:
    merged = dict(existing)
    merged.update(incoming)
    return {aid: text for aid, text in merged.items() if text}


def _min_lock_iso(locks: dict[int, str]) -> str | None:
    if not locks:
        return None
    moments: list[tuple[datetime, str]] = []
    for text in locks.values():
        parsed = _parse_iso(text)
        if parsed is not None:
            moments.append((parsed, text))
    if not moments:
        return None
    moments.sort(key=lambda item: item[0])
    return moments[0][1]


def _parse_iso(text: str) -> datetime | None:
    if not isinstance(text, str):
        return None
    candidate = text.strip()
    if not candidate:
        return None
    try:
        normalised = f"{candidate[:-1]}+00:00" if candidate.endswith("Z") else candidate
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _serialise_locks(locks: dict[int, str]) -> dict[str, str]:
    return {str(aid): text for aid, text in locks.items() if text}


def merge_new(prev: list[dict], cur: list[dict]) -> list[dict]:
    by_id: dict[int, dict[str, Any]] = {
        int(x["id"]): dict(x) for x in prev if isinstance(x.get("id"), int)
    }
    for raw in cur:
        gift_id = int(raw.get("id", 0) or 0)
        if gift_id <= 0:
            continue
        lock_payload = raw.get("locked_until_by_account")
        incoming_locks = _normalise_locks(lock_payload)
        inactive_ids = _inactive_lock_ids(lock_payload)
        existing = by_id.get(gift_id)
        payload = dict(raw)
        if existing is not None:
            existing_locks = _normalise_locks(existing.get("locked_until_by_account"))
            merged_locks = _merge_locks(existing_locks, incoming_locks)
            for acc_id in inactive_ids:
                merged_locks.pop(acc_id, None)
            if merged_locks:
                payload["locked_until_by_account"] = _serialise_locks(merged_locks)
                min_lock = _min_lock_iso(merged_locks)
                if min_lock:
                    payload["locked_until_date"] = min_lock
                else:
                    payload.pop("locked_until_date", None)
            else:
                payload.pop("locked_until_by_account", None)
                payload.pop("locked_until_date", None)
        else:
            if incoming_locks:
                payload["locked_until_by_account"] = _serialise_locks(incoming_locks)
                min_lock = _min_lock_iso(incoming_locks)
                if min_lock:
                    payload["locked_until_date"] = min_lock
            else:
                payload.pop("locked_until_by_account", None)
        by_id[gift_id] = payload
    return sorted(by_id.values(), key=lambda x: (x.get("price", 0), x["id"]))


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
                    tuple(
                        sorted(
                            (
                                int(k),
                                (v.strip() if isinstance(v, str) else None),
                            )
                            for k, v in (it.get("locked_until_by_account") or {}).items()
                            if _is_int_key(k)
                        )
                    ),
                    it.get("sticker_file_id"),
                    it.get("sticker_mime"),
                )
            ).encode("utf-8")
        )
    return m.hexdigest()
