from __future__ import annotations

import pytest
from backend.app import create_app
from backend.infrastructure.db import ENGINE, Base, SessionLocal
from backend.infrastructure.db.models import SessionToken, User


@pytest.fixture(autouse=True)
def reset_database() -> None:
    Base.metadata.drop_all(bind=ENGINE)
    Base.metadata.create_all(bind=ENGINE)
    yield
    Base.metadata.drop_all(bind=ENGINE)


def test_register_login_logout_flow() -> None:
    app = create_app()

    with app.test_client() as client:
        register = client.post(
            "/api/auth/register", json={"username": "alice", "password": "secret123"}
        )
        assert register.status_code == 200

        login = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})
        assert login.status_code == 200
        token_cookie = login.headers.get("Set-Cookie")
        assert token_cookie and "auth_token=" in token_cookie

        assert client.get_cookie("auth_token")
        logout = client.delete("/api/auth/logout")
        assert logout.status_code == 200

    session = SessionLocal()
    try:
        assert session.query(User).count() == 1
        assert session.query(SessionToken).count() == 0
    finally:
        session.close()
