"""Application level error hierarchy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ApplicationError(Exception):
    """Base error for predictable business failures."""

    message: str
    status_code: int = 400
    code: str = "application_error"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message
