# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from typing import Protocol


class ISessionStorage(Protocol):
    def get_session_path(self, user_id: int, phone: str) -> str: ...

    def purge_session(self, session_path: str) -> None: ...

