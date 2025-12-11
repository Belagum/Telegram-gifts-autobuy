from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock

import pytest
from flask import Flask

from backend.application.use_cases.users.register_user import \
    RegisterUserUseCase
from backend.domain.users.entities import User
from backend.interfaces.http.controllers.auth_controller import AuthController
from backend.shared.middleware.error_handler import configure_error_handling


@pytest.fixture()
def flask_app() -> Flask:
    app = Flask(__name__)
    configure_error_handling(app)
    return app


def test_register_endpoint_sets_cookie(flask_app: Flask) -> None:
    register_called: dict[str, tuple[str, str]] = {}

    class StubRegister:
        def execute(self, username: str, password: str) -> tuple[User, str]:
            register_called["args"] = (username, password)
            return (
                User(
                    id=1,
                    username=username,
                    password_hash="hash",
                    created_at=datetime.now(UTC),
                ),
                "token123",
            )

    controller = AuthController(
        register_use_case=cast(RegisterUserUseCase, StubRegister()),
        login_use_case=MagicMock(),
        logout_use_case=MagicMock(),
    )
    flask_app.register_blueprint(controller.as_blueprint())

    with flask_app.test_client() as client:
        response = client.post(
            "/api/auth/register", json={"username": "alice", "password": "secret123"}
        )

    assert response.status_code == 200
    assert register_called["args"] == ("alice", "secret123")
    assert response.headers["Set-Cookie"].startswith("auth_token=")


def test_login_invalid_payload_returns_422(flask_app: Flask) -> None:
    controller = AuthController(
        register_use_case=MagicMock(),
        login_use_case=MagicMock(),
        logout_use_case=MagicMock(),
    )
    flask_app.register_blueprint(controller.as_blueprint())

    with flask_app.test_client() as client:
        response = client.post("/api/auth/login", json={"username": "a"})

    assert response.status_code == 422
    payload = response.get_json()
    assert payload["error"] == "validation_error"
