"""Flask middleware for consistent error handling."""

from __future__ import annotations

from flask import Flask

from backend.shared.errors import register_error_handler


def configure_error_handling(app: Flask) -> None:
    register_error_handler(app)
