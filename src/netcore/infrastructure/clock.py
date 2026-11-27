"""Clock implementations."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """UTC wall clock."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)


class FixedClock:
    """Deterministic clock for tests."""

    def __init__(self, value: datetime) -> None:
        self._value = value

    def now(self) -> datetime:
        """Return the fixed time."""
        return self._value

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        from datetime import timedelta

        self._value += timedelta(seconds=seconds)
