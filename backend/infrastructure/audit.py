# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from backend.shared.logging import logger


class AuditAction(str, Enum):
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGIN_LOCKED = "login_locked"
    LOGOUT = "logout"
    REGISTER = "register"
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_UPDATED = "account_updated"
    ACCOUNT_DELETED = "account_deleted"

    # API profiles
    API_PROFILE_CREATED = "api_profile_created"
    API_PROFILE_DELETED = "api_profile_deleted"
    API_PROFILE_RENAMED = "api_profile_renamed"

    # Settings
    SETTINGS_UPDATED = "settings_updated"
    BOT_TOKEN_UPDATED = "bot_token_updated"

    # Security
    PASSWORD_CHANGED = "password_changed"
    SESSION_REVOKED = "session_revoked"
    ENCRYPTION_KEY_ROTATED = "encryption_key_rotated"

    # Channels
    CHANNEL_CREATED = "channel_created"
    CHANNEL_UPDATED = "channel_updated"
    CHANNEL_DELETED = "channel_deleted"
    CHANNEL_ADDED = "channel_added"
    CHANNEL_REMOVED = "channel_removed"

    # Gifts
    GIFT_PURCHASED = "gift_purchased"
    GIFT_PURCHASE_FAILED = "gift_purchase_failed"
    GIFT_SENT = "gift_sent"
    GIFT_SEND_FAILED = "gift_send_failed"
    GIFTS_REFRESH = "gifts_refresh"
    GIFTS_AUTO_REFRESH_ENABLED = "gifts_auto_refresh_enabled"
    GIFTS_AUTO_REFRESH_DISABLED = "gifts_auto_refresh_disabled"
    GIFTS_AUTOBUY_COMPLETED = "gifts_autobuy_completed"

    # Accounts
    ACCOUNT_ADDED = "account_added"
    ACCOUNT_REFRESH = "account_refresh"


class AuditLogger:
    @staticmethod
    def log(
        action: AuditAction,
        user_id: int | None = None,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
        success: bool = True,
    ) -> None:
        timestamp = datetime.now(UTC)

        safe_details = _sanitize_details(details) if details else {}

        level = "info" if success else "warning"
        log_message = (
            f"AUDIT: {action.value} | "
            f"user_id={user_id} | "
            f"ip={ip_address} | "
            f"success={success}"
        )

        if safe_details:
            log_message += f" | details={safe_details}"

        if level == "info":
            logger.info(log_message)
        else:
            logger.warning(log_message)

        _store_audit_log(
            timestamp=timestamp,
            action=action.value,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            details=safe_details,
        )


def _sanitize_details(details: dict[str, Any]) -> dict[str, Any]:
    sensitive_keys = {
        "password",
        "token",
        "api_hash",
        "bot_token",
        "session_path",
        "phone",
        "secret",
        "key",
    }

    sanitized = {}
    for key, value in details.items():
        key_lower = key.lower()

        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value

    return sanitized


audit = AuditLogger()


def audit_log(
    action: AuditAction,
    user_id: int | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
    success: bool = True,
) -> None:
    audit.log(action, user_id, ip_address, details, success)


def _store_audit_log(
    timestamp: datetime,
    action: str,
    user_id: int | None,
    ip_address: str | None,
    success: bool,
    details: dict[str, Any],
) -> None:
    try:
        from backend.infrastructure.db.models import AuditLog
        from backend.infrastructure.db.session import SessionLocal

        db = SessionLocal()
        try:
            details_json = json.dumps(details) if details else None

            log_entry = AuditLog(
                timestamp=timestamp,
                action=action,
                user_id=user_id,
                ip_address=ip_address,
                success=success,
                details_json=details_json,
            )

            db.add(log_entry)
            db.commit()
        except Exception as db_error:
            db.rollback()
            logger.warning(f"Failed to store audit log in database: {db_error}")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to import database for audit logging: {e}")


__all__ = [
    "AuditAction",
    "AuditLogger",
    "audit",
    "audit_log",
]
