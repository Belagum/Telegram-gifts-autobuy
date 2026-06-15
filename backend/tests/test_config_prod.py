# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import pytest

from backend.shared.config.settings import AppConfig

STRONG = "s" * 40


def _set_prod_env(monkeypatch, **over):
    env = {
        "APP_ENV": "production",
        "SECRET_KEY": STRONG,
        "COOKIE_SECURE": "true",
        "ENABLE_CSRF": "true",
        "ALLOWED_ORIGINS": "https://a.com",
        "ENABLE_HSTS": "true",
    }
    env.update(over)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_prod_ok_with_secure_settings(monkeypatch):
    _set_prod_env(monkeypatch)
    assert AppConfig().is_production()


def test_prod_fails_without_csrf(monkeypatch):
    _set_prod_env(monkeypatch, ENABLE_CSRF="false")
    with pytest.raises(SystemExit):
        AppConfig()


def test_prod_fails_insecure_cookie(monkeypatch):
    _set_prod_env(monkeypatch, COOKIE_SECURE="false")
    with pytest.raises(SystemExit):
        AppConfig()


def test_prod_fails_wildcard_cors(monkeypatch):
    _set_prod_env(monkeypatch, ALLOWED_ORIGINS="*")
    with pytest.raises(SystemExit):
        AppConfig()


def test_prod_fails_weak_secret(monkeypatch):
    _set_prod_env(monkeypatch, SECRET_KEY="dev")
    with pytest.raises(SystemExit):
        AppConfig()


def test_dev_allows_insecure_settings(monkeypatch):
    _set_prod_env(
        monkeypatch,
        APP_ENV="development",
        SECRET_KEY="dev",
        COOKIE_SECURE="false",
        ENABLE_CSRF="false",
        ALLOWED_ORIGINS="*",
    )
    assert not AppConfig().is_production()
