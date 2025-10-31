# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig


from pyrogram.errors import RPCError

# Мапинг классов ошибок Pyrogram на коды для фронтенда
TELEGRAM_ERROR_CODES: dict[str, str] = {
    # Auth errors (400)
    "ApiIdInvalid": "API_ID_INVALID",
    "ApiIdPublishedFlood": "API_ID_PUBLISHED_FLOOD",
    "PhoneNumberInvalid": "PHONE_NUMBER_INVALID",
    "PhoneNumberBanned": "PHONE_NUMBER_BANNED",
    "PhoneNumberFlood": "PHONE_NUMBER_FLOOD",
    "PhoneNumberOccupied": "PHONE_NUMBER_OCCUPIED",
    "PhoneNumberUnoccupied": "PHONE_NUMBER_UNOCCUPIED",
    "PhoneCodeEmpty": "PHONE_CODE_EMPTY",
    "PhoneCodeExpired": "PHONE_CODE_EXPIRED",
    "PhoneCodeHashEmpty": "PHONE_CODE_HASH_EMPTY",
    "PhoneCodeInvalid": "PHONE_CODE_INVALID",
    "SessionPasswordNeeded": "SESSION_PASSWORD_NEEDED",
    "PasswordHashInvalid": "PASSWORD_HASH_INVALID",
    "PasswordEmpty": "PASSWORD_EMPTY",
    
    # Network/connection errors (420, 500)
    "FloodWait": "FLOOD_WAIT",
    "SlowmodeWait": "SLOWMODE_WAIT",
    "AuthKeyUnregistered": "AUTH_KEY_UNREGISTERED",
    "AuthKeyInvalid": "AUTH_KEY_INVALID",
    "SessionRevoked": "SESSION_REVOKED",
    "UserDeactivated": "USER_DEACTIVATED",
    "UserDeactivatedBan": "USER_DEACTIVATED_BAN",
    
    # Peer/user errors (400)
    "PeerIdInvalid": "PEER_ID_INVALID",
    "UsernameInvalid": "USERNAME_INVALID",
    "UsernameNotOccupied": "USERNAME_NOT_OCCUPIED",
    "UsernameOccupied": "USERNAME_OCCUPIED",
    "UserIdInvalid": "USER_ID_INVALID",
    "UserNotMutualContact": "USER_NOT_MUTUAL_CONTACT",
    "UserIsBlocked": "USER_IS_BLOCKED",
    "UserIsBot": "USER_IS_BOT",
    
    # Channel/chat errors
    "ChannelInvalid": "CHANNEL_INVALID",
    "ChannelPrivate": "CHANNEL_PRIVATE",
    "ChatAdminRequired": "CHAT_ADMIN_REQUIRED",
    "ChatWriteForbidden": "CHAT_WRITE_FORBIDDEN",
    
    # Gift/sticker errors
    "PremiumAccountRequired": "PREMIUM_ACCOUNT_REQUIRED",
    "StickerIdInvalid": "STICKER_ID_INVALID",
    
    # Rate limiting
    "TakeoutInvalid": "TAKEOUT_INVALID",
    "Timeout": "TIMEOUT",
    
    # Generic errors
    "BadRequest": "BAD_REQUEST",
    "Unauthorized": "UNAUTHORIZED",
    "Forbidden": "FORBIDDEN",
    "InternalServerError": "INTERNAL_SERVER_ERROR",
}


ERROR_CATEGORIES = {
    "auth": [
        "API_ID_INVALID",
        "API_ID_PUBLISHED_FLOOD",
        "PHONE_NUMBER_INVALID",
        "PHONE_NUMBER_BANNED",
        "PHONE_NUMBER_FLOOD",
        "PHONE_CODE_EXPIRED",
        "PHONE_CODE_INVALID",
        "PHONE_CODE_EMPTY",
        "SESSION_PASSWORD_NEEDED",
        "PASSWORD_HASH_INVALID",
        "PASSWORD_EMPTY",
    ],
    "session": [
        "AUTH_KEY_UNREGISTERED",
        "AUTH_KEY_INVALID",
        "SESSION_REVOKED",
        "USER_DEACTIVATED",
        "USER_DEACTIVATED_BAN",
    ],
    "rate_limit": [
        "FLOOD_WAIT",
        "SLOWMODE_WAIT",
        "PHONE_NUMBER_FLOOD",
        "API_ID_PUBLISHED_FLOOD",
    ],
    "peer": [
        "PEER_ID_INVALID",
        "USER_ID_INVALID",
        "USERNAME_INVALID",
        "USER_IS_BLOCKED",
        "USER_NOT_MUTUAL_CONTACT",
    ],
}


def map_telegram_error(error: RPCError) -> tuple[str, dict | None]:
    error_class_name = error.__class__.__name__
    error_code = TELEGRAM_ERROR_CODES.get(error_class_name, error_class_name)
    
    context = {}
    
    if error_class_name == "FloodWait":
        wait_seconds = getattr(error, "value", None)
        if wait_seconds:
            context["wait_seconds"] = wait_seconds
    
    elif error_class_name == "SlowmodeWait":
        wait_seconds = getattr(error, "value", None)
        if wait_seconds:
            context["wait_seconds"] = wait_seconds
    
    if hasattr(error, "MESSAGE"):
        context["telegram_message"] = error.MESSAGE
    
    return error_code, context if context else None


def get_error_category(error_code: str) -> str:
    for category, codes in ERROR_CATEGORIES.items():
        if error_code in codes:
            return category
    return "unknown"


def is_retryable_error(error_code: str) -> bool:
    non_retryable = {
        "API_ID_INVALID",
        "PHONE_NUMBER_BANNED",
        "USER_DEACTIVATED",
        "USER_DEACTIVATED_BAN",
        "SESSION_REVOKED",
        "AUTH_KEY_INVALID",
    }
    return error_code not in non_retryable

