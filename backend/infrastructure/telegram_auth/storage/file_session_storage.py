# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import glob
import os
import time
from pathlib import Path

from backend.infrastructure.telegram_auth.exceptions import StorageError
from backend.shared.config import load_config
from backend.shared.logging import logger


class FileSessionStorage:
    def __init__(self, base_directory: str | Path | None = None) -> None:
        if base_directory is None:
            config = load_config()
            base_directory = config.sessions_dir

        self._base_directory = str(base_directory)
        self._ensure_base_directory()

        logger.debug(f"FileSessionStorage: initialized base_dir={self._base_directory}")

    def _ensure_base_directory(self) -> None:
        try:
            os.makedirs(self._base_directory, exist_ok=True)
        except OSError as e:
            raise StorageError(
                f"Failed to create base directory: {self._base_directory}",
                error_code="directory_creation_failed",
            ) from e

    def get_session_path(self, user_id: int, phone: str) -> str:
        user_dir = os.path.join(self._base_directory, f"user_{user_id}")

        try:
            os.makedirs(user_dir, exist_ok=True)
        except OSError as e:
            logger.exception(
                f"FileSessionStorage: failed to create user_dir={user_dir}"
            )
            raise StorageError(
                f"Failed to create user directory for user_id={user_id}",
                error_code="user_directory_creation_failed",
            ) from e

        session_path = os.path.join(user_dir, f"{phone}.session")

        logger.debug(
            f"FileSessionStorage: session path prepared "
            f"user_id={user_id} phone={phone} path={session_path}"
        )

        return session_path

    def purge_session(self, session_path: str) -> None:
        logger.info(f"FileSessionStorage: purging session path={session_path}")

        files_to_remove = [
            session_path,
            session_path + "-journal",
            session_path + "-shm",
            session_path + "-wal",
        ]

        for file_path in files_to_remove:
            self._remove_file(file_path)

        try:
            base, _ = os.path.splitext(session_path)
            pattern = base + "*.session*"

            for file_path in glob.glob(pattern):
                self._remove_file(file_path)

        except Exception:
            logger.exception(
                f"FileSessionStorage: glob purge failed "
                f"base={os.path.splitext(session_path)[0]}"
            )

    def _remove_file(self, file_path: str) -> None:
        max_attempts = 3
        retry_delay = 0.1  # 100ms

        for attempt in range(max_attempts):
            try:
                os.remove(file_path)
                logger.debug(f"FileSessionStorage: removed file path={file_path}")
                return
            except FileNotFoundError:
                logger.debug(f"FileSessionStorage: file not found path={file_path}")
                return
            except PermissionError:
                if attempt < max_attempts - 1:
                    logger.debug(
                        f"FileSessionStorage: permission denied (attempt {attempt + 1}/{max_attempts}) "
                        f"path={file_path}, retrying..."
                    )
                    time.sleep(retry_delay)
                else:
                    logger.warning(
                        f"FileSessionStorage: permission denied after {max_attempts} attempts "
                        f"path={file_path}. File may be in use by another process."
                    )
                    return
            except Exception:
                logger.exception(
                    f"FileSessionStorage: failed to remove path={file_path}"
                )
                return
