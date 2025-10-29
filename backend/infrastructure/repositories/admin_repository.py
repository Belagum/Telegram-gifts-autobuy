# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

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


class SQLAlchemyAuditLogRepository(AuditLogRepository):
    def __init__(self, session: Session) -> None:
        self._session = session
    
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
        query = self._session.query(AuditLog)
        
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
        logs = (
            self._session.query(AuditLog)
            .filter(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
            .all()
        )
        return [self._to_domain(log) for log in logs]
    
    def get_by_action(self, action: str, limit: int = 100) -> list[AuditLogEntry]:
        logs = (
            self._session.query(AuditLog)
            .filter(AuditLog.action == action)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
            .all()
        )
        return [self._to_domain(log) for log in logs]
    
    def get_all_actions(self) -> list[str]:
        actions = (
            self._session.query(AuditLog.action)
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
    def __init__(self, session: Session) -> None:
        self._session = session
    
    def get_suspicious_activities(
        self, limit: int = 50
    ) -> list[SuspiciousActivity]:
        activities: list[SuspiciousActivity] = []
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        
        failed_logins_by_ip = (
            self._session.query(
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
            self._session.query(
                AuditLog.user_id,
                func.count(AuditLog.id).label("count"),
                func.min(AuditLog.timestamp).label("first_seen"),
                func.max(AuditLog.timestamp).label("last_seen"),
            )
            .filter(
                AuditLog.action == "login_locked",
                AuditLog.timestamp >= cutoff,
            )
            .group_by(AuditLog.user_id)
            .order_by(desc("last_seen"))
            .limit(limit)
            .all()
        )
        
        for user_id, count, first_seen, last_seen in locked_accounts:
            username = None
            if user_id:
                user = self._session.query(User).filter(User.id == user_id).first()
                username = user.username if user else None
            
            activities.append(
                SuspiciousActivity(
                    severity="medium",
                    activity_type="account_locked",
                    description=f"Account locked due to failed attempts",
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
            self._session.query(
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
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        
        stats_query = (
            self._session.query(
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
                self._session.query(AuditLog)
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
        users = self._session.query(User).order_by(User.id).all()
        result: list[UserInfo] = []
        
        for user in users:
            last_login_log = (
                self._session.query(AuditLog)
                .filter(
                    AuditLog.user_id == user.id,
                    AuditLog.action == "login_success",
                )
                .order_by(desc(AuditLog.timestamp))
                .first()
            )
            
            last_login = last_login_log.timestamp if last_login_log else None
            
            is_locked = _tracker.is_locked(user.username)
            failed_attempts = _tracker.get_failed_attempts_count(user.username)
            
            first_log = (
                self._session.query(AuditLog)
                .filter(AuditLog.user_id == user.id)
                .order_by(AuditLog.timestamp)
                .first()
            )
            created_at = first_log.timestamp if first_log else None
            
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
        cutoff_24h = datetime.now(UTC) - timedelta(hours=24)
        cutoff_7d = datetime.now(UTC) - timedelta(days=7)
        
        total_users = self._session.query(func.count(User.id)).scalar() or 0
        
        total_logs = self._session.query(func.count(AuditLog.id)).scalar() or 0
        
        logs_24h = (
            self._session.query(func.count(AuditLog.id))
            .filter(AuditLog.timestamp >= cutoff_24h)
            .scalar()
            or 0
        )
        
        failed_logins_24h = (
            self._session.query(func.count(AuditLog.id))
            .filter(
                AuditLog.action == "login_failed",
                AuditLog.timestamp >= cutoff_24h,
            )
            .scalar()
            or 0
        )
        
        successful_logins_24h = (
            self._session.query(func.count(AuditLog.id))
            .filter(
                AuditLog.action == "login_success",
                AuditLog.timestamp >= cutoff_24h,
            )
            .scalar()
            or 0
        )
        
        active_sessions = (
            self._session.query(func.count(SessionToken.id))
            .filter(SessionToken.expires_at > datetime.now(UTC))
            .scalar()
            or 0
        )
        
        errors_7d = (
            self._session.query(func.count(AuditLog.id))
            .filter(
                AuditLog.success == False,  # noqa: E712
                AuditLog.timestamp >= cutoff_7d,
            )
            .scalar()
            or 0
        )
        
        most_active = (
            self._session.query(
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

