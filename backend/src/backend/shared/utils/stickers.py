# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations


def sticker_ext(mime: str | None) -> str:
    m = (mime or "").lower()
    if "tgsticker" in m:
        return ".tgs"
    if "webm" in m:
        return ".webm"
    if "webp" in m:
        return ".webp"
    return ".bin"
