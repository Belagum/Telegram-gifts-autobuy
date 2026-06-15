# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import sys
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class _EnvSettings(BaseSettings):
    """База для вложенных конфигов: читает env и .env по alias-именам."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_by_name=True,
        extra="ignore",
    )


class DatabaseConfig(_EnvSettings):
    url: str = Field("sqlite:///app.db", alias="DATABASE_URL")
    pool_size: int = Field(10, ge=1, alias="DATABASE_POOL_SIZE")
    max_overflow: int = Field(5, ge=0, alias="DATABASE_MAX_OVERFLOW")
    pool_timeout: float = Field(30.0, ge=0.1, alias="DATABASE_POOL_TIMEOUT")


class ResilienceConfig(_EnvSettings):
    default_timeout: float = Field(15.0, ge=0.1, alias="RESILIENCE_TIMEOUT")
    max_retries: int = Field(3, ge=0, alias="RESILIENCE_RETRIES")
    backoff_base: float = Field(0.5, ge=0.1, alias="RESILIENCE_BACKOFF_BASE")
    backoff_cap: float = Field(8.0, ge=0.1, alias="RESILIENCE_BACKOFF_CAP")
    circuit_fail_threshold: int = Field(5, ge=1, alias="RESILIENCE_CIRCUIT_THRESHOLD")
    circuit_reset_timeout: float = Field(60.0, ge=1.0, alias="RESILIENCE_CIRCUIT_RESET")


class SecurityConfig(_EnvSettings):
    # Cookie security
    cookie_secure: bool = Field(False, alias="COOKIE_SECURE")
    cookie_samesite: str = Field("Strict", alias="COOKIE_SAMESITE")

    # CORS (NoDecode: парсим как CSV в _parse_origins, не как JSON)
    allowed_origins: Annotated[list[str], NoDecode] = Field(["*"], alias="ALLOWED_ORIGINS")

    # CSRF protection
    enable_csrf: bool = Field(False, alias="ENABLE_CSRF")

    # Rate limiting
    enable_rate_limit: bool = Field(True, alias="ENABLE_RATE_LIMIT")
    rate_limit_requests: int = Field(10, alias="RL_LIMIT")
    rate_limit_window: float = Field(60.0, alias="RL_WINDOW")

    # Число доверенных reverse-proxy хопов для X-Forwarded-For.
    # 0 = прямой доступ, заголовок игнорируется (берётся remote_addr).
    trusted_proxy_count: int = Field(0, alias="TRUSTED_PROXY_COUNT", ge=0)

    # HSTS
    enable_hsts: bool = Field(False, alias="ENABLE_HSTS")

    # Session lifetime (in seconds, default 7 days)
    session_lifetime: int = Field(604800, alias="SESSION_LIFETIME", ge=60)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "cookie_secure",
        "enable_csrf",
        "enable_rate_limit",
        "enable_hsts",
        mode="before",
    )
    @classmethod
    def _parse_bool(cls, value: str | bool) -> bool:
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes")
        return bool(value)


def _database_config_factory() -> DatabaseConfig:
    return DatabaseConfig()  # type: ignore[call-arg]


def _resilience_config_factory() -> ResilienceConfig:
    return ResilienceConfig()  # type: ignore[call-arg]


def _security_config_factory() -> SecurityConfig:
    return SecurityConfig()  # type: ignore[call-arg]


class AppConfig(BaseSettings):
    app_env: str = Field("development", alias="APP_ENV")
    secret_key: str = Field("dev", alias="SECRET_KEY")
    admin_username: str | None = Field(None, alias="ADMIN_USERNAME")
    gifts_dir: Path = Field(Path("backend/instance/gifts_data"), alias="GIFTS_DIR")
    sessions_dir: Path = Field(Path("backend/instance/sessions"), alias="SESSIONS_DIR")
    gifts_accs_ttl: int = Field(60, alias="GIFTS_ACCS_TTL", ge=1)
    debug_logging: bool = Field(False, alias="DEBUG_LOGGING")

    database: DatabaseConfig = Field(default_factory=_database_config_factory)
    resilience: ResilienceConfig = Field(default_factory=_resilience_config_factory)
    security: SecurityConfig = Field(default_factory=_security_config_factory)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    @field_validator("gifts_dir", "sessions_dir", mode="after")
    def _ensure_paths(cls, value: Any) -> Any:  # noqa: N805
        if isinstance(value, Path):
            value.mkdir(parents=True, exist_ok=True)
        return value

    @field_validator("debug_logging", mode="before")
    @classmethod
    def _parse_debug_logging(cls, value: str | bool) -> bool:
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes")
        return bool(value)

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "AppConfig":
        if not self.is_production():
            return self

        errors = []
        if self.secret_key in ("dev", "development", "test", ""):
            errors.append(
                'SECRET_KEY небезопасен. Сгенерируйте: python -c "import secrets; '
                'print(secrets.token_urlsafe(32))"'
            )
        if not self.security.enable_csrf:
            errors.append("CSRF выключен. Установите ENABLE_CSRF=true")
        if not self.security.cookie_secure:
            errors.append("Cookie Secure выключен. Установите COOKIE_SECURE=true (нужен HTTPS)")
        if "*" in self.security.allowed_origins:
            errors.append("CORS разрешает '*'. Укажите явные ALLOWED_ORIGINS=https://...")

        if errors:
            print("\n❌ CRITICAL SECURITY ERRORS (production):", file=sys.stderr)
            for err in errors:
                print(f"   - {err}", file=sys.stderr)
            sys.exit(1)

        if not self.security.enable_hsts:
            print(
                "\n⚠️  HSTS выключен (ENABLE_HSTS=true рекомендуется для HTTPS)\n",
                file=sys.stderr,
            )

        return self

    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "prod")


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    return AppConfig()  # type: ignore[call-arg]


__all__ = ["AppConfig", "load_config"]
