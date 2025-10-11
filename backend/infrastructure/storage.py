# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""File storage adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from backend.shared.logging import logger


class StoragePort(Protocol):
    """Protocol for storage operations."""

    def read_bytes(self, path: str) -> bytes: ...

    def write_bytes(self, path: str, data: bytes) -> None: ...


class LocalFileStorage(StoragePort):
    """Stores files on local filesystem within configured root."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        path = (self._root / relative_path).resolve()
        if not str(path).startswith(str(self._root.resolve())):
            msg = "Attempted directory traversal outside storage root"
            raise ValueError(msg)
        return path

    def read_bytes(self, path: str) -> bytes:
        file_path = self._resolve(path)
        logger.debug(f"storage: read path={file_path}")
        return file_path.read_bytes()

    def write_bytes(self, path: str, data: bytes) -> None:
        file_path = self._resolve(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        logger.debug(f"storage: write path={file_path} size={len(data)}")


__all__ = ["StoragePort", "LocalFileStorage"]
