"""HTTP controller for authentication endpoints."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
from pydantic import ValidationError

from backend.application.use_cases.users.login_user import LoginUserUseCase
from backend.application.use_cases.users.logout_user import LogoutUserUseCase
from backend.application.use_cases.users.register_user import RegisterUserUseCase
from backend.interfaces.http.dto.auth import AuthSuccessDTO, LoginRequestDTO, RegisterRequestDTO
from backend.shared.errors.base import ValidationError as DTOValidationError
from backend.shared.logging import logger


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

    def register(self) -> tuple[Response, int]:
        try:
            dto = RegisterRequestDTO.model_validate(request.get_json(silent=True) or {})
        except ValidationError as exc:
            raise DTOValidationError(message=str(exc)) from exc
        user, token = self._register_use_case.execute(dto.username, dto.password)
        payload = AuthSuccessDTO().model_dump()
        response = jsonify(payload)
        response.set_cookie(
            "auth_token",
            token,
            httponly=True,
            samesite="Lax",
            secure=False,
            max_age=60 * 60 * 24 * 7,
        )
        logger.info(f"auth.register: ok user_id={user.id}")
        return response, 200

    def login(self) -> tuple[Response, int]:
        try:
            dto = LoginRequestDTO.model_validate(request.get_json(silent=True) or {})
        except ValidationError as exc:
            raise DTOValidationError(message=str(exc)) from exc
        token = self._login_use_case.execute(dto.username, dto.password)
        payload = AuthSuccessDTO().model_dump()
        response = jsonify(payload)
        response.set_cookie(
            "auth_token",
            token,
            httponly=True,
            samesite="Lax",
            secure=False,
            max_age=60 * 60 * 24 * 7,
        )
        logger.info(f"auth.login: ok username={dto.username}")
        return response, 200

    def logout(self) -> tuple[Response, int]:
        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.cookies.get("auth_token", "")
        self._logout_use_case.execute(token)
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
