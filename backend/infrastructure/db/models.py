# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from datetime import UTC, datetime, timedelta

from backend.infrastructure.db.encrypted_types import EncryptedString
from backend.infrastructure.db.session import Base
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.sqltypes import Boolean


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (UniqueConstraint("user_id", "channel_id", name="u_user_channel"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    price_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    supply_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    supply_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    accounts: Mapped[list["Account"]] = relationship(
        "Account", back_populates="user", cascade="all,delete"
    )
    apis: Mapped[list["ApiProfile"]] = relationship(
        "ApiProfile", back_populates="user", cascade="all,delete"
    )
    gifts_autorefresh: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # Encrypted: bot token is sensitive data
    bot_token: Mapped[str | None] = mapped_column(EncryptedString(512), nullable=True)
    notify_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    buy_target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)  # NEW
    buy_target_on_fail_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )


class SessionToken(Base):
    __tablename__ = "session_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ApiProfile(Base):
    __tablename__ = "api_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "api_id", name="u_user_api_id"),
        # Note: api_hash uniqueness constraint removed as encrypted values won't match
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    api_id: Mapped[int] = mapped_column(Integer)
    # Encrypted: API hash is sensitive credential
    api_hash: Mapped[str] = mapped_column(EncryptedString(512))
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    user: Mapped["User"] = relationship("User", back_populates="apis")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="api_profile")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        # Note: phone uniqueness constraint removed as encrypted values won't match
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    api_profile_id: Mapped[int] = mapped_column(
        ForeignKey("api_profiles.id", ondelete="CASCADE"), index=True
    )
    # Encrypted: phone number is PII (Personal Identifiable Information)
    phone: Mapped[str] = mapped_column(EncryptedString(256))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stars_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    is_premium: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    premium_until: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Encrypted: session path may contain sensitive info
    session_path: Mapped[str] = mapped_column(EncryptedString(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    user: Mapped["User"] = relationship("User", back_populates="accounts")
    api_profile: Mapped["ApiProfile"] = relationship("ApiProfile", back_populates="accounts")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    success: Mapped[bool] = mapped_column(Boolean, index=True)
    details_json: Mapped[str | None] = mapped_column(String(2048), nullable=True)


def token_default_exp(days: int = 7) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)
