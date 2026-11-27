"""User-visible audit events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from netcore.domain.enums import EventCategory, Severity


@dataclass(frozen=True, slots=True)
class NetworkEvent:
    """An audit event persisted in the ``events`` table."""

    timestamp: datetime
    severity: Severity
    category: EventCategory
    message: str
    device_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    id: int | None = None


@dataclass(frozen=True, slots=True)
class TrafficEvent(NetworkEvent):
    """An event describing simulated traffic."""

    link_id: int | None = None
    direction: str | None = None
    dropped: int = 0
