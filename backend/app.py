# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import atexit
import os
import threading

from flask import Flask
from flask_cors import CORS

from backend.db import SessionLocal, init_db
from backend.logger import bind_flask, logger, setup_logging
from backend.models import User
from backend.routes.account import bp_acc
from backend.routes.auth import bp_auth
from backend.routes.channels import bp_channels
from backend.routes.gifts import bp_gifts
from backend.routes.misc import bp_misc
from backend.routes.settings import bp_settings
from backend.services.gifts_service import GIFTS_THREADS, start_user_gifts, stop_user_gifts

_BOOTSTRAPPED = threading.Event()


def _bootstrap_gifts_workers() -> int:
    db = SessionLocal()
    try:
        ids = [uid for (uid,) in db.query(User.id).filter(User.gifts_autorefresh.is_(True)).all()]
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
    setup_logging()
    app = Flask(__name__)
    bind_flask(app)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(bp_misc)
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_acc)
    app.register_blueprint(bp_gifts)
    app.register_blueprint(bp_settings)
    app.register_blueprint(bp_channels)

    if _should_boot() and not _BOOTSTRAPPED.is_set():
        _BOOTSTRAPPED.set()
        threading.Thread(target=_bootstrap_gifts_workers, daemon=True).start()
        atexit.register(_stop_all_gifts)

    logger.info("Flask app initialized")
    return app


app = create_app()
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me"),
    SESSION_PERMANENT=True,
)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
