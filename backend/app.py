# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Flask application factory."""

import atexit
import os
import threading
import time

from flask import Flask, Response, g, request
from flask_cors import CORS
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from backend.config import load_config
from backend.db import SessionLocal, init_db
from backend.infrastructure.health import check_database
from backend.logger import bind_flask, logger, setup_logging
from backend.models import User
from backend.routes.account import bp_acc
from backend.routes.auth import bp_auth
from backend.routes.channels import bp_channels
from backend.routes.gifts import bp_gifts
from backend.routes.misc import bp_misc
from backend.routes.settings import bp_settings
from backend.services.gifts_service import GIFTS_THREADS, start_user_gifts, stop_user_gifts

_config = load_config()
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
    app.config.update(
        SECRET_KEY=_config.secret_key,
        SESSION_PERMANENT=True,
    )

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(bp_misc)
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_acc)
    app.register_blueprint(bp_gifts)
    app.register_blueprint(bp_settings)
    app.register_blueprint(bp_channels)

    @app.before_request
    def _start_timer() -> None:
        g._request_start = time.perf_counter()

    @app.after_request
    def _record_metrics(response: Response) -> Response:
        start = getattr(g, "_request_start", None)
        if start is not None:
            duration = time.perf_counter() - start
            endpoint = request.endpoint or "unknown"
            status = str(response.status_code)
            from backend.infrastructure.observability import REQUEST_COUNTER, REQUEST_LATENCY

            REQUEST_LATENCY.observe(duration)
            REQUEST_COUNTER.labels(endpoint=endpoint, status=status).inc()
        return response

    @app.get("/metrics")
    def metrics() -> Response:
        payload = generate_latest()
        return Response(payload, mimetype=CONTENT_TYPE_LATEST)

    @app.get("/healthz")
    def health() -> Response:
        return Response("ok", mimetype="text/plain")

    @app.get("/readyz")
    def ready() -> Response:
        check_database()
        return Response("ready", mimetype="text/plain")

    if _should_boot() and not _BOOTSTRAPPED.is_set():
        _BOOTSTRAPPED.set()
        threading.Thread(target=_bootstrap_gifts_workers, daemon=True).start()
        atexit.register(_stop_all_gifts)

    logger.info("Flask app initialized")
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
