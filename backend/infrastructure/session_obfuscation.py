# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path


def generate_session_filename(
    user_id: int, account_id: int, phone: str | None = None
) -> str:
    data = f"{user_id}:{account_id}:{phone or ''}"
    hash_digest = hashlib.sha256(data.encode()).hexdigest()

    obfuscated = hash_digest[:12]

    return f"sess_{obfuscated}"


def generate_random_session_filename() -> str:
    random_bytes = secrets.token_bytes(6)
    random_hex = random_bytes.hex()
    return f"sess_{random_hex}"


def get_session_directory(base_path: Path | str, user_id: int) -> Path:
    base = Path(base_path)

    user_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:2]
    user_dir = base / f"user_{user_hash}"

    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def build_session_path(
    base_path: Path | str,
    user_id: int,
    account_id: int,
    phone: str | None = None,
    extension: str = "session",
) -> str:
    user_dir = get_session_directory(base_path, user_id)
    filename = generate_session_filename(user_id, account_id, phone)

    return str(user_dir / f"{filename}.{extension}")


__all__ = [
    "generate_session_filename",
    "generate_random_session_filename",
    "get_session_directory",
    "build_session_path",
]
