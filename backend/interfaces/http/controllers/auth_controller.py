# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
from pydantic import ValidationError

from backend.application.use_cases.users.login_user import LoginUserUseCase
from backend.application.use_cases.users.logout_user import LogoutUserUseCase
from backend.application.use_cases.users.register_user import \
    RegisterUserUseCase
from backend.infrastructure.audit import AuditAction, audit_log
from backend.interfaces.http.dto.auth import (AuthSuccessDTO, LoginRequestDTO,
                                              RegisterRequestDTO)
from backend.shared.config import load_config
from backend.shared.errors.validation import raise_validation_error
from backend.shared.logging import logger
from backend.shared.middleware.csrf import \
    configure_csrf  # noqa: F401 (import side-effect for type hints)
from backend.shared.middleware.rate_limit import rate_limit


def _get_client_ip() -> str | None:
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip_address and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()
    return ip_address


class AuthController:
    def __init__(
        self,
        *,
        register_use_case: RegisterUserUseCase,
        login_use_case: LoginUserUseCase,
        logout_use_case: LogoutUserUseCase,
    ) -> None:
        self._register_use_case = register_use_case
        self._login_use_case = login_use_case
        self._logout_use_case = logout_use_case

    @rate_limit(limit=5, window_seconds=60.0)
    def register(self) -> tuple[Response, int]:
        try:
            dto = RegisterRequestDTO.model_validate(request.get_json(silent=True) or {})
        except ValidationError as exc:
            raise_validation_error(exc)

        user, token = self._register_use_case.execute(dto.username, dto.password)

        audit_log(
            AuditAction.REGISTER,
            user_id=user.id,
            ip_address=_get_client_ip(),
            details={"username": dto.username},
            success=True,
        )

        payload = AuthSuccessDTO().model_dump()
        response = jsonify(payload)
        config = load_config()
        response.set_cookie(
            "auth_token",
            token,
            httponly=True,
            samesite=config.security.cookie_samesite,
            secure=config.security.cookie_secure,
            max_age=60 * 60 * 24 * 7,
        )
        try:
            import secrets as _secrets

            csrf_token = _secrets.token_urlsafe(32)
        except Exception:
            csrf_token = ""
        if csrf_token:
            response.set_cookie(
                "csrf_token",
                csrf_token,
                httponly=False,
                samesite=config.security.cookie_samesite,
                secure=config.security.cookie_secure,
                max_age=60 * 60 * 24 * 7,
            )
        logger.info(f"auth.register: ok user_id={user.id}")
        return response, 200

    @rate_limit(limit=10, window_seconds=60.0)
    def login(self) -> tuple[Response, int]:
        try:
            dto = LoginRequestDTO.model_validate(request.get_json(silent=True) or {})
        except ValidationError as exc:
            raise_validation_error(exc)

        ip_address = _get_client_ip()

        try:
            token = self._login_use_case.execute(dto.username, dto.password, ip_address)
            audit_log(
                AuditAction.LOGIN_SUCCESS,
                user_id=None,
                ip_address=ip_address,
                details={"username": dto.username, "remember_me": dto.remember_me},
                success=True,
            )
        except Exception as exc:
            audit_log(
                AuditAction.LOGIN_FAILED,
                user_id=None,
                ip_address=ip_address,
                details={"username": dto.username, "error": str(exc)},
                success=False,
            )
            raise

        payload = AuthSuccessDTO().model_dump()
        response = jsonify(payload)

        config = load_config()
        remember_max_age = 60 * 60 * 24 * 7 if dto.remember_me else None
        response.set_cookie(
            "auth_token",
            token,
            httponly=True,
            samesite=config.security.cookie_samesite,
            secure=config.security.cookie_secure,
            max_age=remember_max_age,
        )
        try:
            import secrets as _secrets

            csrf_token = _secrets.token_urlsafe(32)
        except Exception:
            csrf_token = ""
        if csrf_token:
            response.set_cookie(
                "csrf_token",
                csrf_token,
                httponly=False,
                samesite=config.security.cookie_samesite,
                secure=config.security.cookie_secure,
                max_age=60 * 60 * 24 * 7,
            )
        logger.info(
            f"auth.login: ok username={dto.username} remember_me={dto.remember_me}"
        )
        return response, 200

    def logout(self) -> tuple[Response, int]:
        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.cookies.get("auth_token", "")

        self._logout_use_case.execute(token)

        audit_log(
            AuditAction.LOGOUT,
            user_id=None,
            ip_address=_get_client_ip(),
            details={},
            success=True,
        )

        payload = AuthSuccessDTO().model_dump()
        response = jsonify(payload)
        response.delete_cookie("auth_token")
        logger.info("auth.logout: ok")
        return response, 200

    def as_blueprint(self) -> Blueprint:
        bp = Blueprint("auth", __name__, url_prefix="/api/auth")
        bp.add_url_rule("/register", view_func=self.register, methods=["POST"])
        bp.add_url_rule("/login", view_func=self.login, methods=["POST"])
        bp.add_url_rule("/logout", view_func=self.logout, methods=["DELETE"])
        return bp
