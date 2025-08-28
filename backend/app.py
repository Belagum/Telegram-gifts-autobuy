# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import os

from flask import Flask
from flask_cors import CORS

from backend.routes.gifts import bp_gifts
from backend.routes.settings import bp_settings
from .db import init_db
from .routes.auth_routes import bp_auth
from .routes.account_routes import bp_acc
from .routes.misc_routes import bp_misc
from .logger import setup_logging, bind_flask, logger


def create_app() -> Flask:
    # БД
    init_db()

    # Логирование
    setup_logging()
    app = Flask(__name__)
    bind_flask(app)

    # Flask
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(bp_misc)
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_acc)
    app.register_blueprint(bp_gifts)
    app.register_blueprint(bp_settings)

    logger.info("Flask app initialized")
    return app

app = create_app()
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me"),
    SESSION_PERMANENT=True,
)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
