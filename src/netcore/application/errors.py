"""User-safe application errors."""

from __future__ import annotations

from netcore.domain.errors import NetCoreError


class ApplicationError(Exception):
    """Wraps a domain or infrastructure error for the TUI."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


def as_application_error(exc: Exception) -> ApplicationError:
    """Map an exception to an ApplicationError without leaking internals."""
    if isinstance(exc, ApplicationError):
        return exc
    if isinstance(exc, NetCoreError):
        return ApplicationError(exc.code, exc.message)
    return ApplicationError("APP500", f"Unexpected error: {exc}")
