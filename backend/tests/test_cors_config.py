# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from backend.shared.middleware.cors import build_cors_kwargs


def test_explicit_origins_enable_credentials():
    kw = build_cors_kwargs(["https://a.com", "https://b.com"])
    assert kw["supports_credentials"] is True
    assert kw["resources"] == {r"/api/*": {"origins": ["https://a.com", "https://b.com"]}}


def test_wildcard_disables_credentials():
    kw = build_cors_kwargs(["*"])
    assert "supports_credentials" not in kw


def test_wildcard_mixed_with_explicit_disables_credentials():
    # самый опасный кейс: '*' + явный origin не должен включать credentials
    kw = build_cors_kwargs(["*", "https://a.com"])
    assert "supports_credentials" not in kw


def test_empty_origins_no_credentials():
    kw = build_cors_kwargs([])
    assert "supports_credentials" not in kw
