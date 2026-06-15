# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations


def build_cors_kwargs(origins: list[str]) -> dict[str, object]:
    """Собирает kwargs для flask_cors.CORS.

    supports_credentials включаем ТОЛЬКО когда заданы явные origins и среди них
    нет '*'. Спецификация CORS запрещает отдавать credentials с wildcard-origin,
    а flask-cors в этом случае начал бы отражать любой Origin вместе с cookie —
    это полный обход CORS. Поэтому при наличии '*' credentials всегда выключены.
    """
    has_wildcard = "*" in origins
    explicit = [o for o in origins if o != "*"]
    kwargs: dict[str, object] = {"resources": {r"/api/*": {"origins": origins}}}
    if explicit and not has_wildcard:
        kwargs["supports_credentials"] = True
    return kwargs


__all__ = ["build_cors_kwargs"]
