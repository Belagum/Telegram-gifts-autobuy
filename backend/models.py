from sqlalchemy import Integer, String, ForeignKey, BigInteger, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timedelta, timezone
from .db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="user", cascade="all,delete")
    apis: Mapped[list["ApiProfile"]] = relationship("ApiProfile", back_populates="user", cascade="all,delete")

class SessionToken(Base):
    __tablename__ = "session_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class ApiProfile(Base):
    __tablename__ = "api_profiles"
    __table_args__ = (
        UniqueConstraint("user_id","api_id", name="u_user_api_id"),
        UniqueConstraint("user_id","api_hash", name="u_user_api_hash"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    api_id: Mapped[int] = mapped_column(Integer)
    api_hash: Mapped[str] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    user: Mapped["User"] = relationship("User", back_populates="apis")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="api_profile")

class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id","phone", name="u_user_phone"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    api_profile_id: Mapped[int] = mapped_column(ForeignKey("api_profiles.id", ondelete="CASCADE"), index=True)
    phone: Mapped[str] = mapped_column(String(32))
    username: Mapped[str|None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str|None] = mapped_column(String(128), nullable=True)
    stars_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    stars_nanos: Mapped[int] = mapped_column(Integer, default=0)
    session_path: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    user: Mapped["User"] = relationship("User", back_populates="accounts")
    api_profile: Mapped["ApiProfile"] = relationship("ApiProfile", back_populates="accounts")

def token_default_exp(days:int=7)->datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)
