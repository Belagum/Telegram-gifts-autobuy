# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiCredentials:
    api_id: int
    api_hash: str


@dataclass(frozen=True)
class LoginContext:
    user_id: int
    api_profile_id: int
    phone: str


@dataclass
class LoginSession:
    login_id: str
    user_id: int
    api_profile_id: int
    phone: str
    session_path: str
    api_credentials: ApiCredentials
    phone_code_hash: str | None = None


@dataclass(frozen=True)
class AccountData:
    telegram_id: int | None
    username: str | None
    first_name: str | None
    stars_amount: int
    is_premium: bool
    premium_until: str | None


@dataclass(frozen=True)
class LoginResult:
    success: bool
    error: str | None = None
    error_code: str | None = None
    http_status: int = 200
    data: dict[str, Any] | None = None
    should_close_modal: bool = False

    @classmethod
    def ok(cls, data: dict[str, Any] | None = None) -> "LoginResult":
        return cls(success=True, data=data or {})

    @classmethod
    def fail(
        cls,
        error: str,
        error_code: str | None = None,
        http_status: int = 400,
        data: dict[str, Any] | None = None,
        should_close_modal: bool = False
    ) -> "LoginResult":
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            http_status=http_status,
            data=data,
            should_close_modal=should_close_modal
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        
        if self.success:
            if self.data:
                result.update(self.data)
            if not result:
                result["ok"] = True
        else:
            result["error"] = self.error
            if self.error_code:
                result["error_code"] = self.error_code
            if self.data:
                result["context"] = self.data
            result["http"] = self.http_status
            if self.should_close_modal:
                result["should_close_modal"] = True
        
        return result


@dataclass(frozen=True)
class TwoFactorRequired:
    need_2fa: bool = True

