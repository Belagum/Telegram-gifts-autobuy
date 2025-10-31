# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.domain.admin.repositories import (
    AdminRepository,
    AuditLogEntry,
    AuditLogRepository,
    ErrorStats,
    SuspiciousActivity,
    UserInfo,
)
from backend.infrastructure.auth.login_attempts import _tracker
from backend.infrastructure.db.models import AuditLog, SessionToken, User
from backend.infrastructure.unit_of_work import unit_of_work_scope
from sqlalchemy import desc, func
from sqlalchemy.orm import Session


class SQLAlchemyAuditLogRepository(AuditLogRepository):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
    
    def list_logs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        action: str | None = None,
        user_id: int | None = None,
        ip_address: str | None = None,
        success: bool | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[AuditLogEntry], int]:
        with unit_of_work_scope(self._session_factory) as session:
            query = session.query(AuditLog)
            
            if action:
                query = query.filter(AuditLog.action == action)
            if user_id is not None:
                query = query.filter(AuditLog.user_id == user_id)
            if ip_address:
                query = query.filter(AuditLog.ip_address == ip_address)
            if success is not None:
                query = query.filter(AuditLog.success == success)
            if start_date:
                query = query.filter(AuditLog.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditLog.timestamp <= end_date)
            
            total_count = query.count()
            
            query = query.order_by(desc(AuditLog.timestamp))
            query = query.offset(offset).limit(limit)
            
            logs = [self._to_domain(log) for log in query.all()]
        
        return logs, total_count
    
    def get_by_user(self, user_id: int, limit: int = 100) -> list[AuditLogEntry]:
        with unit_of_work_scope(self._session_factory) as session:
            logs = (
                session.query(AuditLog)
                .filter(AuditLog.user_id == user_id)
                .order_by(desc(AuditLog.timestamp))
                .limit(limit)
                .all()
            )
        return [self._to_domain(log) for log in logs]
    
    def get_by_action(self, action: str, limit: int = 100) -> list[AuditLogEntry]:
        with unit_of_work_scope(self._session_factory) as session:
            logs = (
                session.query(AuditLog)
                .filter(AuditLog.action == action)
                .order_by(desc(AuditLog.timestamp))
                .limit(limit)
                .all()
            )
        return [self._to_domain(log) for log in logs]
    
    def get_all_actions(self) -> list[str]:
        with unit_of_work_scope(self._session_factory) as session:
            actions = (
                session.query(AuditLog.action)
                .distinct()
                .order_by(AuditLog.action)
                .all()
            )
        return [action[0] for action in actions]
    
    def _to_domain(self, model: AuditLog) -> AuditLogEntry:
        details = {}
        if model.details_json:
            try:
                details = json.loads(model.details_json)
            except json.JSONDecodeError:
                details = {"raw": model.details_json}
        
        return AuditLogEntry(
            id=model.id,
            timestamp=model.timestamp,
            action=model.action,
            user_id=model.user_id,
            ip_address=model.ip_address,
            success=model.success,
            details=details,
        )


class SQLAlchemyAdminRepository(AdminRepository):    
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
    
    def get_suspicious_activities(
        self, limit: int = 50
    ) -> list[SuspiciousActivity]:
        with unit_of_work_scope(self._session_factory) as session:
            activities: list[SuspiciousActivity] = []
            cutoff = datetime.now(UTC) - timedelta(hours=24)
            
            failed_logins_by_ip = (
                session.query(
                    AuditLog.ip_address,
                    func.count(AuditLog.id).label("count"),
                    func.min(AuditLog.timestamp).label("first_seen"),
                    func.max(AuditLog.timestamp).label("last_seen"),
                )
                .filter(
                    AuditLog.action == "login_failed",
                    AuditLog.timestamp >= cutoff,
                    AuditLog.ip_address.isnot(None),
                )
                .group_by(AuditLog.ip_address)
                .having(func.count(AuditLog.id) >= 5)
                .order_by(desc("count"))
                .limit(limit)
                .all()
            )
            
            for ip, count, first_seen, last_seen in failed_logins_by_ip:
                activities.append(
                    SuspiciousActivity(
                        severity="high",
                        activity_type="multiple_failed_logins",
                        description=f"Multiple failed login attempts from IP {ip}",
                        user_id=None,
                        username=None,
                        ip_address=ip,
                        count=count,
                        first_seen=first_seen,
                        last_seen=last_seen,
                        details={"threshold": 5},
                    )
                )
            
            locked_accounts = (
                session.query(
                    AuditLog.user_id,
                    User.username,
                    func.count(AuditLog.id).label("count"),
                    func.min(AuditLog.timestamp).label("first_seen"),
                    func.max(AuditLog.timestamp).label("last_seen"),
                )
                .outerjoin(User, AuditLog.user_id == User.id)
                .filter(
                    AuditLog.action == "login_locked",
                    AuditLog.timestamp >= cutoff,
                )
                .group_by(AuditLog.user_id, User.username)
                .order_by(desc("last_seen"))
                .limit(limit)
                .all()
            )
            
            for user_id, username, count, first_seen, last_seen in locked_accounts:
                activities.append(
                    SuspiciousActivity(
                        severity="medium",
                        activity_type="account_locked",
                        description="Account locked due to failed attempts",
                        user_id=user_id,
                        username=username,
                        ip_address=None,
                        count=count,
                        first_seen=first_seen,
                        last_seen=last_seen,
                        details={},
                    )
                )
            
            errors_by_ip = (
                session.query(
                    AuditLog.ip_address,
                    func.count(AuditLog.id).label("count"),
                    func.min(AuditLog.timestamp).label("first_seen"),
                    func.max(AuditLog.timestamp).label("last_seen"),
                )
                .filter(
                    AuditLog.success == False,  # noqa: E712
                    AuditLog.timestamp >= cutoff,
                    AuditLog.ip_address.isnot(None),
                )
                .group_by(AuditLog.ip_address)
                .having(func.count(AuditLog.id) >= 10)
                .order_by(desc("count"))
                .limit(limit)
                .all()
            )
            
            for ip, count, first_seen, last_seen in errors_by_ip:
                activities.append(
                    SuspiciousActivity(
                        severity="low",
                        activity_type="multiple_errors",
                        description=f"Multiple errors from IP {ip}",
                        user_id=None,
                        username=None,
                        ip_address=ip,
                        count=count,
                        first_seen=first_seen,
                        last_seen=last_seen,
                        details={"threshold": 10},
                    )
                )
            
            severity_order = {"high": 0, "medium": 1, "low": 2}
            activities.sort(key=lambda x: (severity_order[x.severity], -x.count))
            
            return activities[:limit]
    
    def get_error_stats(self, limit: int = 50) -> list[ErrorStats]:
        with unit_of_work_scope(self._session_factory) as session:
            cutoff = datetime.now(UTC) - timedelta(hours=24)
            
            stats_query = (
                session.query(
                    AuditLog.ip_address,
                    func.count(AuditLog.id).label("error_count"),
                    func.count(func.distinct(AuditLog.action)).label("unique_actions"),
                    func.min(AuditLog.timestamp).label("first_error"),
                    func.max(AuditLog.timestamp).label("last_error"),
                )
                .filter(
                    AuditLog.success == False,  # noqa: E712
                    AuditLog.timestamp >= cutoff,
                )
                .group_by(AuditLog.ip_address)
                .order_by(desc("error_count"))
                .limit(limit)
                .all()
            )
            
            result: list[ErrorStats] = []
            
            for ip, error_count, unique_actions, first_error, last_error in stats_query:
                # Get sample errors
                sample_logs = (
                    session.query(AuditLog)
                    .filter(
                        AuditLog.ip_address == ip,
                        AuditLog.success == False,  # noqa: E712
                        AuditLog.timestamp >= cutoff,
                    )
                    .order_by(desc(AuditLog.timestamp))
                    .limit(5)
                    .all()
                )
                
                sample_errors = [log.action for log in sample_logs]
                
                result.append(
                    ErrorStats(
                        ip_address=ip,
                        error_count=error_count,
                        unique_actions=unique_actions,
                        first_error=first_error,
                        last_error=last_error,
                        sample_errors=sample_errors,
                    )
                )
            
            return result
    
    def list_users(self) -> list[UserInfo]:
        with unit_of_work_scope(self._session_factory) as session:
            last_login_subq = (
                session.query(
                    AuditLog.user_id,
                    func.max(AuditLog.timestamp).label("last_login")
                )
                .filter(AuditLog.action == "login_success")
                .group_by(AuditLog.user_id)
                .subquery()
            )
            
            first_log_subq = (
                session.query(
                    AuditLog.user_id,
                    func.min(AuditLog.timestamp).label("created_at")
                )
                .group_by(AuditLog.user_id)
                .subquery()
            )
            
            users_with_stats = (
                session.query(
                    User,
                    last_login_subq.c.last_login,
                    first_log_subq.c.created_at
                )
                .outerjoin(last_login_subq, User.id == last_login_subq.c.user_id)
                .outerjoin(first_log_subq, User.id == first_log_subq.c.user_id)
                .order_by(User.id)
                .all()
            )
            
            result: list[UserInfo] = []
            for user, last_login, created_at in users_with_stats:
                is_locked = _tracker.is_locked(user.username)
                failed_attempts = _tracker.get_failed_attempts_count(user.username)
                
                result.append(
                    UserInfo(
                        id=user.id,
                        username=user.username,
                        is_admin=user.is_admin,
                        created_at=created_at,
                        last_login=last_login,
                        is_locked=is_locked,
                        failed_attempts=failed_attempts,
                    )
                )
            
            return result
    
    def get_dashboard_stats(self) -> dict[str, Any]:
        with unit_of_work_scope(self._session_factory) as session:
            cutoff_24h = datetime.now(UTC) - timedelta(hours=24)
            cutoff_7d = datetime.now(UTC) - timedelta(days=7)
            
            total_users = session.query(func.count(User.id)).scalar() or 0
            
            total_logs = session.query(func.count(AuditLog.id)).scalar() or 0
            
            logs_24h = (
                session.query(func.count(AuditLog.id))
                .filter(AuditLog.timestamp >= cutoff_24h)
                .scalar()
                or 0
            )
            
            failed_logins_24h = (
                session.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.action == "login_failed",
                    AuditLog.timestamp >= cutoff_24h,
                )
                .scalar()
                or 0
            )
            
            successful_logins_24h = (
                session.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.action == "login_success",
                    AuditLog.timestamp >= cutoff_24h,
                )
                .scalar()
                or 0
            )
            
            active_sessions = (
                session.query(func.count(SessionToken.id))
                .filter(SessionToken.expires_at > datetime.now(UTC))
                .scalar()
                or 0
            )
            
            errors_7d = (
                session.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.success == False,  # noqa: E712
                    AuditLog.timestamp >= cutoff_7d,
                )
                .scalar()
                or 0
            )
            
            most_active = (
                session.query(
                    User.username,
                    func.count(AuditLog.id).label("activity_count"),
                )
                .join(AuditLog, AuditLog.user_id == User.id)
                .filter(AuditLog.timestamp >= cutoff_7d)
                .group_by(User.username)
                .order_by(desc("activity_count"))
                .limit(5)
                .all()
            )
            
            most_active_users = [
                {"username": username, "activity_count": count}
                for username, count in most_active
            ]
            
            return {
                "total_users": total_users,
                "total_logs": total_logs,
                "logs_last_24h": logs_24h,
                "failed_logins_24h": failed_logins_24h,
                "successful_logins_24h": successful_logins_24h,
                "active_sessions": active_sessions,
                "errors_last_7d": errors_7d,
                "most_active_users": most_active_users,
            }


__all__ = [
    "SQLAlchemyAuditLogRepository",
    "SQLAlchemyAdminRepository",
]

