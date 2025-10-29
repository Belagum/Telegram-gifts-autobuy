# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    url: str = Field("sqlite:///app.db", alias="DATABASE_URL")
    pool_size: int = Field(10, ge=1, alias="DATABASE_POOL_SIZE")
    max_overflow: int = Field(5, ge=0, alias="DATABASE_MAX_OVERFLOW")
    pool_timeout: float = Field(30.0, ge=0.1, alias="DATABASE_POOL_TIMEOUT")

    model_config = ConfigDict(validate_by_name=True)


class CacheConfig(BaseModel):
    directory: Path = Field(Path("backend/instance/gifts_cache"), alias="GIFTS_CACHE_DIR")
    ttl_seconds: int = Field(3600, ge=1, alias="CACHE_TTL")

    model_config = ConfigDict(validate_by_name=True)


class QueueConfig(BaseModel):
    max_size: int = Field(1000, ge=1, alias="QUEUE_MAX_SIZE")
    visibility_timeout: float = Field(30.0, ge=0.1, alias="QUEUE_VISIBILITY_TIMEOUT")

    model_config = ConfigDict(validate_by_name=True)


class ResilienceConfig(BaseModel):
    default_timeout: float = Field(15.0, ge=0.1, alias="RESILIENCE_TIMEOUT")
    max_retries: int = Field(3, ge=0, alias="RESILIENCE_RETRIES")
    backoff_base: float = Field(0.5, ge=0.1, alias="RESILIENCE_BACKOFF_BASE")
    backoff_cap: float = Field(8.0, ge=0.1, alias="RESILIENCE_BACKOFF_CAP")
    circuit_fail_threshold: int = Field(5, ge=1, alias="RESILIENCE_CIRCUIT_THRESHOLD")
    circuit_reset_timeout: float = Field(60.0, ge=1.0, alias="RESILIENCE_CIRCUIT_RESET")

    model_config = ConfigDict(validate_by_name=True)


class ObservabilityConfig(BaseModel):
    metrics_enabled: bool = Field(True, alias="METRICS_ENABLED")
    tracing_enabled: bool = Field(False, alias="TRACING_ENABLED")
    service_name: str = Field("giftbuyer-backend", alias="SERVICE_NAME")

    model_config = ConfigDict(validate_by_name=True)


class SecurityConfig(BaseModel):
    # Cookie security
    cookie_secure: bool = Field(False, alias="COOKIE_SECURE")
    cookie_samesite: str = Field("Strict", alias="COOKIE_SAMESITE")

    # CORS
    allowed_origins: list[str] = Field(["*"], alias="ALLOWED_ORIGINS")

    # CSRF protection
    enable_csrf: bool = Field(False, alias="ENABLE_CSRF")

    # Rate limiting
    enable_rate_limit: bool = Field(True, alias="ENABLE_RATE_LIMIT")
    rate_limit_requests: int = Field(10, alias="RL_LIMIT")
    rate_limit_window: float = Field(60.0, alias="RL_WINDOW")

    # HSTS
    enable_hsts: bool = Field(False, alias="ENABLE_HSTS")

    model_config = ConfigDict(validate_by_name=True)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "cookie_secure", "enable_csrf", "enable_rate_limit", "enable_hsts", mode="before"
    )
    @classmethod
    def _parse_bool(cls, value: str | bool) -> bool:
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes")
        return bool(value)


def _database_config_factory() -> DatabaseConfig:
    return DatabaseConfig()  # type: ignore[call-arg]


def _cache_config_factory() -> CacheConfig:
    return CacheConfig()  # type: ignore[call-arg]


def _queue_config_factory() -> QueueConfig:
    return QueueConfig()  # type: ignore[call-arg]


def _resilience_config_factory() -> ResilienceConfig:
    return ResilienceConfig()  # type: ignore[call-arg]


def _observability_config_factory() -> ObservabilityConfig:
    return ObservabilityConfig()  # type: ignore[call-arg]


def _security_config_factory() -> SecurityConfig:
    return SecurityConfig()  # type: ignore[call-arg]


class AppConfig(BaseSettings):
    app_env: str = Field("development", alias="APP_ENV")
    secret_key: str = Field("dev", alias="SECRET_KEY")
    admin_username: str | None = Field(None, alias="ADMIN_USERNAME")
    gifts_dir: Path = Field(Path("gifts_data"), alias="GIFTS_DIR")
    gifts_accs_ttl: int = Field(60, alias="GIFTS_ACCS_TTL", ge=1)
    debug_logging: bool = Field(False, alias="DEBUG_LOGGING")

    database: DatabaseConfig = Field(default_factory=_database_config_factory)
    cache: CacheConfig = Field(default_factory=_cache_config_factory)
    queue: QueueConfig = Field(default_factory=_queue_config_factory)
    resilience: ResilienceConfig = Field(default_factory=_resilience_config_factory)
    observability: ObservabilityConfig = Field(default_factory=_observability_config_factory)
    security: SecurityConfig = Field(default_factory=_security_config_factory)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    @field_validator("gifts_dir", mode="after")
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

        if self.secret_key in ("dev", "development", "test", ""):
            print(
                "\n❌ CRITICAL SECURITY ERROR: Insecure SECRET_KEY detected in production!\n"
                "   SECRET_KEY must be a strong random value in production.\n"
                "   Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n",
                file=sys.stderr,
            )
            sys.exit(1)

        warnings = []
        if not self.security.enable_csrf:
            warnings.append("⚠️  CSRF protection is DISABLED")
        if not self.security.cookie_secure:
            warnings.append("⚠️  Cookie Secure flag is DISABLED (use HTTPS!)")
        if "*" in self.security.allowed_origins:
            warnings.append("⚠️  CORS allows wildcard (*) origins")
        if not self.security.enable_hsts:
            warnings.append("⚠️  HSTS is DISABLED (recommended for HTTPS)")

        if warnings:
            print("\n⚠️  PRODUCTION SECURITY WARNINGS:", file=sys.stderr)
            for warning in warnings:
                print(f"   {warning}", file=sys.stderr)
            print(
                "   Consider enabling these security features in production.\n",
                file=sys.stderr,
            )

        return self

    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "prod")


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    return AppConfig()  


__all__ = ["AppConfig", "load_config"]
