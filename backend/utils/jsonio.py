from __future__ import annotations

import json
from typing import Any
from .fs import write_json_atomic


def read_json_list_of_dicts(path: str) -> list[dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, list):
                return [x for x in loaded if isinstance(x, dict)]
            return []
    except Exception:
        return []


def write_json_list(path: str, data: list[dict[str, Any]]) -> None:
    write_json_atomic(path, data)
