# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import pytest

import backend.infrastructure.telegram_auth.services.session_manager as sm_mod
from backend.infrastructure.telegram_auth.exceptions import LoginNotFoundError
from backend.infrastructure.telegram_auth.models.dto import (ApiCredentials,
                                                             LoginSession)
from backend.infrastructure.telegram_auth.services.session_manager import \
    SessionManager


def _make_session() -> LoginSession:
    return LoginSession(
        login_id="",
        user_id=1,
        api_profile_id=1,
        phone="+10000000000",
        session_path="/tmp/x.session",
        api_credentials=ApiCredentials(api_id=1, api_hash="h"),
    )


def test_session_evicted_after_ttl(monkeypatch):
    monkeypatch.setattr(sm_mod, "_LOGIN_TTL_SECONDS", -1)  # всё мгновенно протухает
    mgr = SessionManager()
    login_id = mgr.create_session(_make_session())
    with pytest.raises(LoginNotFoundError):
        mgr.get_session(login_id)


def test_session_alive_within_ttl():
    mgr = SessionManager()
    login_id = mgr.create_session(_make_session())
    assert mgr.get_session(login_id).login_id == login_id
    assert mgr.get_active_sessions_count() == 1
