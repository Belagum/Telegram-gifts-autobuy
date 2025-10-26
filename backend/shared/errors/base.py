# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, cast


@dataclass(slots=True)
class AppError(Exception):
    code: str
    status: HTTPStatus
    context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.code)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": self.code}
        if self.context:
            payload["context"] = dict(self.context)
        return payload


class DomainError(AppError):
    def __init__(
        self,
        *,
        code: str | None = None,
        status: HTTPStatus | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        resolved_code = code or cast(str, getattr(self, "code", "domain_error"))
        resolved_status = status or cast(
            HTTPStatus, getattr(self, "status", HTTPStatus.BAD_REQUEST)
        )
        super().__init__(code=resolved_code, status=resolved_status, context=context)


class InfrastructureError(AppError):
    def __init__(
        self,
        code: str = "infrastructure_error",
        *,
        status: HTTPStatus | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        resolved_status = status or HTTPStatus.INTERNAL_SERVER_ERROR
        super().__init__(code=code, status=resolved_status, context=context)


class ValidationError(AppError):
    def __init__(
        self,
        code: str = "validation_error",
        *,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
            context=context,
        )


class ChannelNotFoundError(AppError):
    def __init__(self, channel_id: int) -> None:
        super().__init__(
            code="channel_not_found",
            status=HTTPStatus.NOT_FOUND,
            context={"channel_id": channel_id},
        )


class DuplicateChannelError(AppError):
    def __init__(self, channel_id: int | str | None) -> None:
        context = None
        if channel_id is not None:
            context = {"channel_id": channel_id}
        super().__init__(
            code="duplicate_channel",
            status=HTTPStatus.CONFLICT,
            context=context,
        )


class BadChannelIdError(AppError):
    def __init__(self, channel_id: str) -> None:
        super().__init__(
            code="bad_channel_id",
            status=HTTPStatus.BAD_REQUEST,
            context={"channel_id": channel_id},
        )


class InvalidBotTokenError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="bot_token_type",
            status=HTTPStatus.BAD_REQUEST,
        )


class InvalidChatIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="notify_chat_id_type",
            status=HTTPStatus.BAD_REQUEST,
        )


class InvalidTargetIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="buy_target_id_type",
            status=HTTPStatus.BAD_REQUEST,
        )


class InvalidFallbackError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="buy_target_on_fail_only_type",
            status=HTTPStatus.BAD_REQUEST,
        )


class InvalidNotifyChatIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="notify_chat_id_invalid",
            status=HTTPStatus.BAD_REQUEST,
        )


class InvalidBuyTargetIdError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="buy_target_id_invalid",
            status=HTTPStatus.BAD_REQUEST,
        )


class InvalidGiftIdError(AppError):
    def __init__(self, gift_id: str) -> None:
        super().__init__(
            code="gift_id_invalid",
            status=HTTPStatus.BAD_REQUEST,
            context={"gift_id": gift_id},
        )


class InvalidAccountIdError(AppError):
    def __init__(self) -> None:
        super().__init__(code="account_id_invalid", status=HTTPStatus.BAD_REQUEST)


class TargetIdRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="target_id_required",
            status=HTTPStatus.BAD_REQUEST,
        )


class TargetIdInvalidError(AppError):
    def __init__(self) -> None:
        super().__init__(code="target_id_invalid", status=HTTPStatus.BAD_REQUEST)


class PeerIdInvalidError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="peer_id_invalid",
            status=HTTPStatus.BAD_REQUEST,
        )


class AccountNotFoundError(AppError):
    def __init__(self, account_id: int) -> None:
        super().__init__(
            code="account_not_found",
            status=HTTPStatus.NOT_FOUND,
            context={"account_id": account_id},
        )


class ApiProfileMissingError(AppError):
    def __init__(self) -> None:
        super().__init__(code="api_profile_missing", status=HTTPStatus.CONFLICT)


class GiftNotFoundError(AppError):
    def __init__(self, gift_id: int) -> None:
        super().__init__(
            code="gift_not_found",
            status=HTTPStatus.NOT_FOUND,
            context={"gift_id": gift_id},
        )


class GiftUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(code="gift_unavailable", status=HTTPStatus.CONFLICT)


class InsufficientBalanceError(AppError):
    def __init__(self, balance: int, price: int) -> None:
        super().__init__(
            code="insufficient_balance",
            status=HTTPStatus.CONFLICT,
            context={"balance": balance, "required": price},
        )


class BadTgsError(AppError):
    def __init__(self) -> None:
        super().__init__(code="bad_tgs", status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
