# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from flask import Blueprint, Response, g, jsonify, request
from pydantic import ValidationError

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
from backend.infrastructure.admin_middleware import require_admin
from backend.interfaces.http.dto.admin import (ActionCategoriesDTO,
                                               AuditLogDTO, AuditLogListDTO,
                                               AuditLogsFilterDTO,
                                               DashboardStatsDTO,
                                               ErrorStatsDTO,
                                               SuspiciousActivityDTO,
                                               UserInfoDTO)
from backend.shared.errors.validation import raise_validation_error
from backend.shared.logging import logger


class AdminController:
    def __init__(
        self,
        *,
        get_audit_logs: GetAuditLogsUseCase,
        get_user_audit: GetUserAuditUseCase,
        get_suspicious_activity: GetSuspiciousActivityUseCase,
        get_error_stats: GetErrorStatsUseCase,
        list_users: ListUsersUseCase,
        unlock_user: UnlockUserUseCase,
        get_dashboard_stats: GetDashboardStatsUseCase,
    ) -> None:
        self._get_audit_logs = get_audit_logs
        self._get_user_audit = get_user_audit
        self._get_suspicious_activity = get_suspicious_activity
        self._get_error_stats = get_error_stats
        self._list_users = list_users
        self._unlock_user = unlock_user
        self._get_dashboard_stats = get_dashboard_stats

    @require_admin
    def audit_logs(self) -> tuple[Response, int]:
        from flask import g

        debug_mode = getattr(g, "debug_mode", False)
        user_id = getattr(g, "user_id", None)

        if debug_mode:
            logger.info(f"admin.audit_logs called by user={user_id}")

        try:
            # Parse query parameters
            params = {
                "limit": request.args.get("limit", 100, type=int),
                "offset": request.args.get("offset", 0, type=int),
                "action": request.args.get("action"),
                "user_id": request.args.get("user_id", type=int),
                "ip_address": request.args.get("ip_address"),
                "success": (
                    request.args.get("success", type=lambda x: x.lower() == "true")
                    if request.args.get("success")
                    else None
                ),
            }

            # Parse dates if provided
            if request.args.get("start_date"):
                from datetime import datetime

                params["start_date"] = datetime.fromisoformat(request.args.get("start_date"))  # type: ignore
            if request.args.get("end_date"):
                from datetime import datetime

                params["end_date"] = datetime.fromisoformat(request.args.get("end_date"))  # type: ignore

            filter_dto = AuditLogsFilterDTO.model_validate(params)
        except ValidationError as exc:
            if debug_mode:
                logger.warning(
                    f"admin.audit_logs validation error for user={user_id}: {exc}"
                )
            raise_validation_error(exc)

        try:
            # Get logs
            logs, total = self._get_audit_logs.execute(
                limit=filter_dto.limit,
                offset=filter_dto.offset,
                action=filter_dto.action,
                user_id=filter_dto.user_id,
                ip_address=filter_dto.ip_address,
                success=filter_dto.success,
                start_date=filter_dto.start_date,
                end_date=filter_dto.end_date,
            )

            # Convert to DTOs
            log_dtos = [AuditLogDTO.model_validate(log) for log in logs]
            result = AuditLogListDTO(
                logs=log_dtos,
                total=total,
                limit=filter_dto.limit,
                offset=filter_dto.offset,
            )

            if debug_mode:
                count = len(logs)
                logger.info(
                    f"admin.audit_logs completed successfully for user={user_id}: returned {count} logs, total={total}"
                )
            else:
                logger.info(
                    f"admin.audit_logs: returned {len(logs)} logs, total={total}"
                )

            return jsonify(result.model_dump()), 200
        except Exception as exc:
            if debug_mode:
                logger.exception(f"admin.audit_logs failed for user={user_id}: {exc}")
            else:
                logger.error(f"admin.audit_logs failed: {type(exc).__name__}")
            raise

    @require_admin
    def action_categories(self) -> tuple[Response, int]:
        from flask import g

        debug_mode = getattr(g, "debug_mode", False)
        user_id = getattr(g, "user_id", None)

        try:
            actions = self._get_audit_logs.get_all_actions()
            result = ActionCategoriesDTO(actions=actions)

            if debug_mode:
                count = len(actions)
                logger.info(
                    f"admin.action_categories completed successfully for user={user_id}: returned {count} categories"
                )
            else:
                logger.info(
                    f"admin.action_categories: returned {len(actions)} categories"
                )

            return jsonify(result.model_dump()), 200
        except Exception as exc:
            if debug_mode:
                logger.exception(
                    f"admin.action_categories failed for user={user_id}: {exc}"
                )
            else:
                logger.error(f"admin.action_categories failed: {type(exc).__name__}")
            raise

    @require_admin
    def user_audit(self, user_id: int) -> tuple[Response, int]:
        from flask import g

        debug_mode = getattr(g, "debug_mode", False)
        admin_user_id = getattr(g, "user_id", None)

        if debug_mode:
            logger.info(
                f"admin.user_audit called by user={admin_user_id} for target_user={user_id}"
            )

        try:
            limit = request.args.get("limit", 100, type=int)
            logs = self._get_user_audit.execute(user_id=user_id, limit=limit)

            log_dtos = [AuditLogDTO.model_validate(log) for log in logs]

            if debug_mode:
                logger.info(
                    f"admin.user_audit completed successfully for user={admin_user_id}: "
                    f"target_user={user_id}, returned {len(logs)} logs"
                )
            else:
                logger.info(
                    f"admin.user_audit: user_id={user_id} returned {len(logs)} logs"
                )

            return jsonify({"logs": [dto.model_dump() for dto in log_dtos]}), 200
        except Exception as exc:
            if debug_mode:
                logger.exception(
                    f"admin.user_audit failed for user={admin_user_id}, target_user={user_id}: {exc}"
                )
            else:
                logger.error(f"admin.user_audit failed: {type(exc).__name__}")
            raise

    @require_admin
    def suspicious_activity(self) -> tuple[Response, int]:
        from flask import g

        debug_mode = getattr(g, "debug_mode", False)
        user_id = getattr(g, "user_id", None)

        if debug_mode:
            logger.info(f"admin.suspicious_activity called by user={user_id}")

        try:
            limit = request.args.get("limit", 50, type=int)
            activities = self._get_suspicious_activity.execute(limit=limit)

            activity_dtos = [
                SuspiciousActivityDTO.model_validate(act) for act in activities
            ]

            if debug_mode:
                count = len(activities)
                logger.info(
                    f"admin.suspicious_activity completed successfully for user={user_id}: returned {count} activities"
                )
            else:
                logger.info(
                    f"admin.suspicious_activity: returned {len(activities)} activities"
                )

            return (
                jsonify({"activities": [dto.model_dump() for dto in activity_dtos]}),
                200,
            )
        except Exception as exc:
            if debug_mode:
                logger.exception(
                    f"admin.suspicious_activity failed for user={user_id}: {exc}"
                )
            else:
                logger.error(f"admin.suspicious_activity failed: {type(exc).__name__}")
            raise

    @require_admin
    def error_stats(self) -> tuple[Response, int]:
        from flask import g

        debug_mode = getattr(g, "debug_mode", False)
        user_id = getattr(g, "user_id", None)

        if debug_mode:
            logger.info(f"admin.error_stats called by user={user_id}")

        try:
            limit = request.args.get("limit", 50, type=int)
            stats = self._get_error_stats.execute(limit=limit)

            stats_dtos = [ErrorStatsDTO.model_validate(stat) for stat in stats]

            if debug_mode:
                count = len(stats)
                logger.info(
                    f"admin.error_stats completed successfully for user={user_id}: returned {count} stat entries"
                )
            else:
                logger.info(f"admin.error_stats: returned {len(stats)} stat entries")

            return jsonify({"stats": [dto.model_dump() for dto in stats_dtos]}), 200
        except Exception as exc:
            if debug_mode:
                logger.exception(f"admin.error_stats failed for user={user_id}: {exc}")
            else:
                logger.error(f"admin.error_stats failed: {type(exc).__name__}")
            raise

    @require_admin
    def users(self) -> tuple[Response, int]:
        from flask import g

        debug_mode = getattr(g, "debug_mode", False)
        user_id = getattr(g, "user_id", None)

        if debug_mode:
            logger.info(f"admin.users called by user={user_id}")

        try:
            users = self._list_users.execute()

            user_dtos = [UserInfoDTO.model_validate(user) for user in users]

            if debug_mode:
                count = len(users)
                logger.info(
                    f"admin.users completed successfully for user={user_id}: returned {count} users"
                )
            else:
                logger.info(f"admin.users: returned {len(users)} users")

            return jsonify({"users": [dto.model_dump() for dto in user_dtos]}), 200
        except Exception as exc:
            if debug_mode:
                logger.exception(f"admin.users failed for user={user_id}: {exc}")
            else:
                logger.error(f"admin.users failed: {type(exc).__name__}")
            raise

    @require_admin
    def unlock_user(self, user_id: int) -> tuple[Response, int]:
        from flask import g

        debug_mode = getattr(g, "debug_mode", False)
        admin_user_id = getattr(g, "user_id", None)

        if debug_mode:
            logger.info(
                f"admin.unlock_user called by user={admin_user_id} for target_user={user_id}"
            )

        try:
            self._unlock_user.execute(user_id=user_id)

            if debug_mode:
                logger.info(
                    f"admin.unlock_user completed successfully for user={admin_user_id}: unlocked user_id={user_id}"
                )
            else:
                logger.info(f"admin.unlock_user: unlocked user_id={user_id}")

            return jsonify({"success": True}), 200
        except Exception as exc:
            if debug_mode:
                logger.exception(
                    f"admin.unlock_user failed for user={admin_user_id}, target_user={user_id}: {exc}"
                )
            else:
                logger.error(f"admin.unlock_user failed: {type(exc).__name__}")
            raise

    @require_admin
    def dashboard_stats(self) -> tuple[Response, int]:
        debug_mode = getattr(g, "debug_mode", False)
        user_id = getattr(g, "user_id", None)

        if debug_mode:
            logger.info(f"admin.dashboard_stats called by user={user_id}")

        try:
            stats = self._get_dashboard_stats.execute()

            stats_dto = DashboardStatsDTO.model_validate(stats)

            if debug_mode:
                logger.info(
                    f"admin.dashboard_stats completed successfully for user={user_id}"
                )
            else:
                logger.info("admin.dashboard_stats: returned dashboard stats")

            return jsonify(stats_dto.model_dump()), 200
        except Exception as exc:
            if debug_mode:
                logger.exception(
                    f"admin.dashboard_stats failed for user={user_id}: {exc}"
                )
            else:
                logger.error(f"admin.dashboard_stats failed: {type(exc).__name__}")
            raise

    def as_blueprint(self) -> Blueprint:
        bp = Blueprint("admin", __name__, url_prefix="/api/admin")

        bp.add_url_rule("/audit-logs", view_func=self.audit_logs, methods=["GET"])
        bp.add_url_rule(
            "/audit-logs/categories", view_func=self.action_categories, methods=["GET"]
        )
        bp.add_url_rule(
            "/audit-logs/user/<int:user_id>",
            view_func=self.user_audit,
            methods=["GET"],
        )
        bp.add_url_rule(
            "/suspicious-activity", view_func=self.suspicious_activity, methods=["GET"]
        )
        bp.add_url_rule("/error-stats", view_func=self.error_stats, methods=["GET"])
        bp.add_url_rule("/users", view_func=self.users, methods=["GET"])
        bp.add_url_rule(
            "/users/<int:user_id>/unlock", view_func=self.unlock_user, methods=["POST"]
        )
        bp.add_url_rule(
            "/dashboard-stats", view_func=self.dashboard_stats, methods=["GET"]
        )

        return bp


__all__ = ["AdminController"]
