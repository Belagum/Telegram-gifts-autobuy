# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import base64
import os
import sys
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from backend.shared.logging import logger


class EncryptionService:
    def __init__(self, key: bytes | None = None) -> None:
        if key is None:
            key = self._load_key_from_env()
        
        self._fernet = Fernet(key)
        logger.info("EncryptionService initialized")
    
    @staticmethod
    def _load_key_from_env() -> bytes:
        key_str = os.getenv("ENCRYPTION_KEY", "")
        
        app_env = os.getenv("APP_ENV", "development").lower()
        is_production = app_env in ("production", "prod")
        
        if not key_str:
            if is_production:
                print(
                    "\n❌ CRITICAL: ENCRYPTION_KEY not set in production!\n"
                    "   Sensitive data cannot be encrypted without a key.\n"
                    "   Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n",
                    file=sys.stderr,
                )
                sys.exit(1)
            else:
                logger.warning(
                    "ENCRYPTION_KEY not set, using fixed development key. "
                    "DO NOT use this in production!"
                )
                dev_key = b"dev-key-for-local-development-only=="
                return base64.urlsafe_b64encode(dev_key.ljust(32, b'='))
        
        try:
            return key_str.encode("utf-8")
        except Exception as exc:
            print(
                f"\n❌ CRITICAL: Invalid ENCRYPTION_KEY format: {exc}\n"
                "   Key must be a valid Fernet key (32 url-safe base64-encoded bytes).\n",
                file=sys.stderr,
            )
            if is_production:
                sys.exit(1)
            raise
    
    def encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None:
            return None
        
        if not isinstance(plaintext, str):
            raise TypeError(f"Expected str, got {type(plaintext).__name__}")
        
        encrypted_bytes = self._fernet.encrypt(plaintext.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")
    
    def decrypt(self, ciphertext: str | None) -> str | None:
        if ciphertext is None:
            return None
        
        if not isinstance(ciphertext, str):
            raise TypeError(f"Expected str, got {type(ciphertext).__name__}")
        
        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt: invalid token or corrupted data") from exc
    
    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode("utf-8")


@lru_cache(maxsize=1)
def get_encryption_service() -> EncryptionService:
    return EncryptionService()


def encrypt_value(plaintext: str | None) -> str | None:
    return get_encryption_service().encrypt(plaintext)


def decrypt_value(ciphertext: str | None) -> str | None:
    return get_encryption_service().decrypt(ciphertext)


__all__ = [
    "EncryptionService",
    "get_encryption_service",
    "encrypt_value",
    "decrypt_value",
]

