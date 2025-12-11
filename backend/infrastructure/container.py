# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from functools import cached_property

from backend.application.services.password_hashing import \
    WerkzeugPasswordHasher
from backend.application.use_cases.admin.get_audit_logs import \
    GetAuditLogsUseCase
from backend.application.use_cases.admin.get_dashboard_stats import \
    GetDashboardStatsUseCase
from backend.application.use_cases.admin.get_error_stats import \
    GetErrorStatsUseCase
from backend.application.use_cases.admin.get_suspicious_activity import \
    GetSuspiciousActivityUseCase
from backend.application.use_cases.admin.get_user_audit import \
    GetUserAuditUseCase
from backend.application.use_cases.admin.list_users import ListUsersUseCase
from backend.application.use_cases.admin.unlock_user import UnlockUserUseCase
from backend.application.use_cases.autobuy import AutobuyUseCase
from backend.application.use_cases.users.login_user import LoginUserUseCase
from backend.application.use_cases.users.logout_user import LogoutUserUseCase
from backend.application.use_cases.users.register_user import \
    RegisterUserUseCase
from backend.infrastructure.db import SessionLocal
from backend.infrastructure.repositories.admin_repository import (
    SQLAlchemyAdminRepository, SQLAlchemyAuditLogRepository)
from backend.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyAccountRepository, SqlAlchemyChannelRepository,
    SqlAlchemyUserSettingsRepository)
from backend.infrastructure.repositories.users.sqlalchemy_user_repository import (
    SqlAlchemySessionTokenRepository, SqlAlchemyUserRepository)
from backend.infrastructure.telegram import (TelegramNotificationAdapter,
                                             TelegramRpcPort)
from backend.interfaces.http.controllers.admin_controller import \
    AdminController
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

    @cached_property
    def account_repository(self) -> SqlAlchemyAccountRepository:
        return SqlAlchemyAccountRepository(SessionLocal)

    @cached_property
    def channel_repository(self) -> SqlAlchemyChannelRepository:
        return SqlAlchemyChannelRepository(SessionLocal)

    @cached_property
    def user_settings_repository(self) -> SqlAlchemyUserSettingsRepository:
        return SqlAlchemyUserSettingsRepository(SessionLocal)

    @cached_property
    def telegram_port(self) -> TelegramRpcPort:
        return TelegramRpcPort()

    @cached_property
    def notification_port(self) -> TelegramNotificationAdapter:
        return TelegramNotificationAdapter()

    @cached_property
    def autobuy_use_case(self) -> AutobuyUseCase:
        return AutobuyUseCase(
            accounts=self.account_repository,
            channels=self.channel_repository,
            telegram=self.telegram_port,
            notifications=self.notification_port,
            settings=self.user_settings_repository,
        )

    # Admin repositories

    @cached_property
    def audit_log_repository(self) -> SQLAlchemyAuditLogRepository:
        return SQLAlchemyAuditLogRepository(SessionLocal)

    @cached_property
    def admin_repository(self) -> SQLAlchemyAdminRepository:
        return SQLAlchemyAdminRepository(SessionLocal)

    # Admin use cases

    @cached_property
    def get_audit_logs_use_case(self) -> GetAuditLogsUseCase:
        return GetAuditLogsUseCase(audit_log_repo=self.audit_log_repository)

    @cached_property
    def get_user_audit_use_case(self) -> GetUserAuditUseCase:
        return GetUserAuditUseCase(audit_log_repo=self.audit_log_repository)

    @cached_property
    def get_suspicious_activity_use_case(self) -> GetSuspiciousActivityUseCase:
        return GetSuspiciousActivityUseCase(admin_repo=self.admin_repository)

    @cached_property
    def get_error_stats_use_case(self) -> GetErrorStatsUseCase:
        return GetErrorStatsUseCase(admin_repo=self.admin_repository)

    @cached_property
    def list_users_use_case(self) -> ListUsersUseCase:
        return ListUsersUseCase(admin_repo=self.admin_repository)

    @cached_property
    def unlock_user_use_case(self) -> UnlockUserUseCase:
        return UnlockUserUseCase(user_repo=self.user_repository)

    @cached_property
    def get_dashboard_stats_use_case(self) -> GetDashboardStatsUseCase:
        return GetDashboardStatsUseCase(admin_repo=self.admin_repository)

    # Admin controller

    @cached_property
    def admin_controller(self) -> AdminController:
        return AdminController(
            get_audit_logs=self.get_audit_logs_use_case,
            get_user_audit=self.get_user_audit_use_case,
            get_suspicious_activity=self.get_suspicious_activity_use_case,
            get_error_stats=self.get_error_stats_use_case,
            list_users=self.list_users_use_case,
            unlock_user=self.unlock_user_use_case,
            get_dashboard_stats=self.get_dashboard_stats_use_case,
        )


container = Container()
