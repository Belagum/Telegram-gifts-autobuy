# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import cast


@dataclass(slots=True)
class AppError(Exception):

    message: str
    code: str
    status: HTTPStatus

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


class DomainError(AppError):

    def __init__(self, message: str | None = None) -> None:
        fallback_message = cast(str, getattr(self, "message", "domain_error"))
        resolved_message = message if message is not None else fallback_message
        resolved_code = cast(str, getattr(self, "code", "domain_error"))
        resolved_status = cast(HTTPStatus, getattr(self, "status", HTTPStatus.BAD_REQUEST))
        super().__init__(
            message=resolved_message,
            code=resolved_code,
            status=resolved_status,
        )


class InfrastructureError(AppError):
    def __init__(self, message: str, code: str = "infrastructure_error") -> None:
        super().__init__(message=message, code=code, status=HTTPStatus.INTERNAL_SERVER_ERROR)


class ValidationError(AppError):
    def __init__(self, message: str, code: str = "validation_error") -> None:
        super().__init__(message=message, code=code, status=HTTPStatus.UNPROCESSABLE_ENTITY)


class ChannelNotFoundError(AppError):
    def __init__(self, channel_id: int) -> None:
        super().__init__(
            message=f"Channel with ID {channel_id} not found",
            code="channel_not_found",
            status=HTTPStatus.NOT_FOUND
        )


class DuplicateChannelError(AppError):
    def __init__(self, channel_id: int) -> None:
        super().__init__(
            message=f"Channel with ID {channel_id} already exists",
            code="duplicate_channel",
            status=HTTPStatus.CONFLICT
        )


class BadChannelIdError(AppError):
    def __init__(self, channel_id: str) -> None:
        super().__init__(
            message=f"Invalid channel ID: {channel_id}",
            code="bad_channel_id",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidBotTokenError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Bot token must be a string",
            code="bot_token_type",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidChatIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Chat ID must be a string or integer",
            code="notify_chat_id_type",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidTargetIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Target ID must be a string or integer",
            code="buy_target_id_type",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidFallbackError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Fallback setting must be a boolean",
            code="buy_target_on_fail_only_type",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidNotifyChatIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid notify chat ID",
            code="notify_chat_id_invalid",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidBuyTargetIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid buy target ID",
            code="buy_target_id_invalid",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidGiftIdError(AppError):
    def __init__(self, gift_id: str) -> None:
        super().__init__(
            message=f"Invalid gift ID: {gift_id}",
            code="gift_id_invalid",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidAccountIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid account ID",
            code="account_id_invalid",
            status=HTTPStatus.BAD_REQUEST
        )


class TargetIdRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Target ID is required",
            code="target_id_required",
            status=HTTPStatus.BAD_REQUEST
        )


class InvalidTargetIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid target ID",
            code="target_id_invalid",
            status=HTTPStatus.BAD_REQUEST
        )


class AccountNotFoundError(AppError):
    def __init__(self, account_id: int) -> None:
        super().__init__(
            message=f"Account with ID {account_id} not found",
            code="account_not_found",
            status=HTTPStatus.NOT_FOUND
        )


class ApiProfileMissingError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="API profile is missing for account",
            code="api_profile_missing",
            status=HTTPStatus.CONFLICT
        )


class GiftNotFoundError(AppError):
    def __init__(self, gift_id: int) -> None:
        super().__init__(
            message=f"Gift with ID {gift_id} not found",
            code="gift_not_found",
            status=HTTPStatus.NOT_FOUND
        )


class GiftUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Gift is unavailable",
            code="gift_unavailable",
            status=HTTPStatus.CONFLICT
        )


class InsufficientBalanceError(AppError):
    def __init__(self, balance: int, price: int) -> None:
        super().__init__(
            message=f"Insufficient balance: {balance}⭐, need {price}⭐",
            code="insufficient_balance",
            status=HTTPStatus.CONFLICT
        )


class BadTgsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid TGS file",
            code="bad_tgs",
            status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        )