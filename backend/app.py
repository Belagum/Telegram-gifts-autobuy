# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import atexit
import importlib
import os
import threading
from datetime import timedelta

from flask import Flask
from typing import Any, Protocol, cast

from backend.infrastructure.admin_setup import setup_admin_user
from backend.infrastructure.container import container
from backend.infrastructure.db import SessionLocal, init_db
from backend.infrastructure.db.models import User
from backend.interfaces.http.controllers.accounts_controller import \
    AccountsController
from backend.interfaces.http.controllers.channels_controller import \
    ChannelsController
from backend.interfaces.http.controllers.gifts_controller import \
    GiftsController
from backend.interfaces.http.controllers.misc_controller import MiscController
from backend.interfaces.http.controllers.settings_controller import \
    SettingsController
from backend.services.gifts_service import (GIFTS_THREADS, start_user_gifts,
                                            stop_user_gifts)
from backend.shared.config import load_config
from backend.shared.logging import logger, setup_logging
from backend.shared.middleware.csrf import configure_csrf
from backend.shared.middleware.error_handler import configure_error_handling
from backend.shared.middleware.request_logger import configure_request_logging

class _CORSCallable(Protocol):
    def __call__(self, app: Flask, **kwargs: Any) -> Any: ...


_flask_cors = importlib.import_module("flask_cors")
CORS = cast(_CORSCallable, _flask_cors.CORS)


_config = load_config()
_BOOTSTRAPPED = threading.Event()


def _bootstrap_gifts_workers() -> int:
    db = SessionLocal()
    try:
        ids = [
            uid
            for (uid,) in db.query(User.id)
            .filter(User.gifts_autorefresh.is_(True))
            .all()
        ]
        for uid in ids:
            start_user_gifts(uid)
        logger.info(f"gifts.bootstrap: started {len(ids)} workers")
        return len(ids)
    finally:
        db.close()


def _stop_all_gifts() -> None:
    for uid in list(GIFTS_THREADS.keys()):
        stop_user_gifts(uid)
    logger.info("gifts.bootstrap: stopped all workers")


def _should_boot() -> bool:
    if os.environ.get("GIFTBUYER_BOOT_WORKERS") == "1":
        return True
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def create_app() -> Flask:
    init_db()
    setup_logging(debug_mode=_config.debug_logging)

    setup_admin_user()

    app = Flask(__name__)
    configure_error_handling(app)
    configure_csrf(app)

    configure_request_logging(app)

    app.config.update(
        SECRET_KEY=_config.secret_key,
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=_config.security.session_lifetime),
    )

    cors_kwargs: dict[str, object] = {
        "resources": {r"/api/*": {"origins": _config.security.allowed_origins}}
    }
    if any(o != "*" for o in _config.security.allowed_origins):
        cors_kwargs["supports_credentials"] = True
    CORS(app, **cors_kwargs)
    app.register_blueprint(MiscController().as_blueprint())
    app.register_blueprint(container.auth_controller.as_blueprint())
    app.register_blueprint(container.admin_controller.as_blueprint())
    app.register_blueprint(AccountsController().as_blueprint())
    app.register_blueprint(GiftsController().as_blueprint())
    app.register_blueprint(SettingsController().as_blueprint())
    app.register_blueprint(ChannelsController().as_blueprint())

    if _should_boot() and not _BOOTSTRAPPED.is_set():
        _BOOTSTRAPPED.set()
        threading.Thread(target=_bootstrap_gifts_workers, daemon=True).start()
        atexit.register(_stop_all_gifts)

    @app.after_request
    def _add_security_headers(resp):
        resp.headers.setdefault("X-Frame-Options", "DENY")

        resp.headers.setdefault("Referrer-Policy", "no-referrer")

        resp.headers.setdefault("X-Content-Type-Options", "nosniff")

        resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")

        resp.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=()",
        )

        resp.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        if _config.security.enable_hsts:
            resp.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )

        return resp

    logger.info("Flask app initialized")
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
