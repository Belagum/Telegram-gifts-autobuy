"""Application dependency container."""

from __future__ import annotations

from functools import cached_property

from backend.application.services.password_hashing import WerkzeugPasswordHasher
from backend.application.use_cases.users.login_user import LoginUserUseCase
from backend.application.use_cases.users.logout_user import LogoutUserUseCase
from backend.application.use_cases.users.register_user import RegisterUserUseCase
from backend.infrastructure.repositories.users.sqlalchemy_user_repository import (
    SqlAlchemySessionTokenRepository,
    SqlAlchemyUserRepository,
)
from backend.interfaces.http.controllers.auth_controller import AuthController


class Container:
    def __init__(self) -> None:
        pass

    @cached_property
    def password_hasher(self) -> WerkzeugPasswordHasher:
        return WerkzeugPasswordHasher()

    @cached_property
    def user_repository(self) -> SqlAlchemyUserRepository:
        return SqlAlchemyUserRepository()

    @cached_property
    def session_token_repository(self) -> SqlAlchemySessionTokenRepository:
        return SqlAlchemySessionTokenRepository()

    @cached_property
    def register_user_use_case(self) -> RegisterUserUseCase:
        return RegisterUserUseCase(
            users=self.user_repository,
            tokens=self.session_token_repository,
            password_hasher=self.password_hasher,
        )

    @cached_property
    def login_user_use_case(self) -> LoginUserUseCase:
        return LoginUserUseCase(
            users=self.user_repository,
            tokens=self.session_token_repository,
            password_hasher=self.password_hasher,
        )

    @cached_property
    def logout_user_use_case(self) -> LogoutUserUseCase:
        return LogoutUserUseCase(tokens=self.session_token_repository)

    @cached_property
    def auth_controller(self) -> AuthController:
        return AuthController(
            register_use_case=self.register_user_use_case,
            login_use_case=self.login_user_use_case,
            logout_use_case=self.logout_user_use_case,
        )


container = Container()
