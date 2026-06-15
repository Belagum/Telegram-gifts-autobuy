# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from pathlib import Path

from flask import request


def etag_for_path(path: Path) -> str:
    st = path.stat()
    return f'W/"{int(st.st_mtime)}-{st.st_size}"'


def client_ip() -> str:
    """IP клиента для rate limit / lockout / audit.

    Если приложение за доверенным прокси, ProxyFix перезаписывает
    ``remote_addr`` значением из X-Forwarded-For. Без прокси ``remote_addr`` —
    это адрес сокета. Сам заголовок X-Forwarded-For мы НЕ читаем, поэтому
    клиент не может его подделать.
    """
    return request.remote_addr or "unknown"
