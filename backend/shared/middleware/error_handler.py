# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from flask import Flask

from backend.shared.errors import register_error_handler


def _noop_csrf(_: Flask) -> None:
    return None


def configure_error_handling(app: Flask) -> None:
    register_error_handler(app)
