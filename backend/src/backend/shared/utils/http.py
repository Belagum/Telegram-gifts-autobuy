# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from pathlib import Path


def etag_for_path(path: Path) -> str:
    st = path.stat()
    return f'W/"{int(st.st_mtime)}-{st.st_size}"'
