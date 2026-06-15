# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from backend.shared.config.settings import DatabaseConfig, SecurityConfig


def test_security_config_reads_env(monkeypatch):
    # регрессия: раньше вложенные конфиги игнорировали переменные окружения
    monkeypatch.setenv("RL_LIMIT", "777")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("ENABLE_CSRF", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.com,https://b.com")
    s = SecurityConfig()
    assert s.rate_limit_requests == 777
    assert s.cookie_secure is True
    assert s.enable_csrf is True
    assert s.allowed_origins == ["https://a.com", "https://b.com"]


def test_database_config_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert DatabaseConfig().url == "postgresql://u:p@h/db"
