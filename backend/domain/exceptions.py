"""Domain-specific exceptions."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain-layer errors."""


class InvariantViolationError(DomainError):
    """Raised when a domain entity invariant is violated."""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.field:
            return f"{self.field}: {super().__str__()}"
        return super().__str__()


# Backwards compatibility alias.
InvariantViolation = InvariantViolationError
