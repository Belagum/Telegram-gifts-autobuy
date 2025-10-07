# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import hashlib
from typing import Any


def merge_new(prev: list[dict], cur: list[dict]) -> list[dict]:
    by_id = {x["id"]: x for x in prev}
    for x in cur:
        by_id[x["id"]] = x
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
                    it.get("sticker_file_id"),
                    it.get("sticker_mime"),
                )
            ).encode("utf-8")
        )
    return m.hexdigest()
