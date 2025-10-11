# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
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


class AppConfig(BaseSettings):

    secret_key: str = Field("dev", alias="SECRET_KEY")
    gifts_dir: Path = Field(Path("gifts_data"), alias="GIFTS_DIR")
    gifts_accs_ttl: int = Field(60, alias="GIFTS_ACCS_TTL", ge=1)

    database: DatabaseConfig = Field(default_factory=lambda: DatabaseConfig())
    cache: CacheConfig = Field(default_factory=lambda: CacheConfig())
    queue: QueueConfig = Field(default_factory=lambda: QueueConfig())
    resilience: ResilienceConfig = Field(default_factory=lambda: ResilienceConfig())
    observability: ObservabilityConfig = Field(default_factory=lambda: ObservabilityConfig())

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    @field_validator("gifts_dir", "cache", mode="after")
    def _ensure_paths(cls, value: Any) -> Any:  # noqa: N805
        if isinstance(value, Path):
            value.mkdir(parents=True, exist_ok=True)
        elif isinstance(value, CacheConfig):
            value.directory.mkdir(parents=True, exist_ok=True)
        return value


@lru_cache(maxsize=1)
def load_config() -> AppConfig:

    return AppConfig()


__all__ = ["AppConfig", "load_config"]
