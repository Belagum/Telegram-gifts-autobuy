"""Shared error hierarchy for the service."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import cast


@dataclass(slots=True)
class AppError(Exception):
    """Base application exception carrying structured metadata."""

    message: str
    code: str
    status: HTTPStatus

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


class DomainError(AppError):
    """Domain-level invariant violation."""

    def __init__(self, message: str | None = None) -> None:
        fallback_message = cast(str, getattr(self, "message", "domain_error"))
        resolved_message = message if message is not None else fallback_message
        resolved_code = cast(str, getattr(self, "code", "domain_error"))
        resolved_status = cast(HTTPStatus, getattr(self, "status", HTTPStatus.BAD_REQUEST))
        super().__init__(
            message=resolved_message,
            code=resolved_code,
            status=resolved_status,
        )


class InfrastructureError(AppError):
    def __init__(self, message: str, code: str = "infrastructure_error") -> None:
        super().__init__(message=message, code=code, status=HTTPStatus.INTERNAL_SERVER_ERROR)


class ValidationError(AppError):
    def __init__(self, message: str, code: str = "validation_error") -> None:
        super().__init__(message=message, code=code, status=HTTPStatus.UNPROCESSABLE_ENTITY)
