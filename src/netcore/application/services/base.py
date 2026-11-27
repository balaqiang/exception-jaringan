"""Shared service plumbing."""

from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import datetime
from typing import Any, ParamSpec, TypeVar

from netcore.application.dto import EventDTO
from netcore.application.errors import ApplicationError
from netcore.application.event_bus import EventBus
from netcore.application.ports import Clock, UnitOfWork
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.errors import NetCoreError
from netcore.domain.events import NetworkEvent

P = ParamSpec("P")
R = TypeVar("R")
UowFactory = Callable[[], UnitOfWork]


def maps_errors(fn: Callable[P, R]) -> Callable[P, R]:
    """Convert domain errors into user-safe ApplicationError instances."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except ApplicationError:
            raise
        except NetCoreError as exc:
            raise ApplicationError(exc.code, exc.message) from exc

    return wrapper


def setting(settings: dict[str, str], key: str, default: int) -> int:
    """Read an integer setting with a safe fallback."""
    try:
        return int(settings.get(key, str(default)))
    except (TypeError, ValueError):
        return default


def make_event(
    now: datetime,
    severity: Severity,
    category: EventCategory,
    message: str,
    *,
    device_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> NetworkEvent:
    """Build a domain event."""
    return NetworkEvent(
        timestamp=now,
        severity=severity,
        category=category,
        message=message,
        device_id=device_id,
        payload=payload or {},
    )


def event_dto(event: NetworkEvent, device_name: str | None = None) -> EventDTO:
    """Map a domain event to a frozen DTO."""
    import json

    return EventDTO(
        event_id=event.id,
        timestamp=event.timestamp.isoformat(timespec="seconds"),
        severity=event.severity.value,
        category=event.category.value,
        device_id=event.device_id,
        device_name=device_name,
        message=event.message,
        payload_json=json.dumps(event.payload, indent=2, default=str),
    )


class ServiceBase:
    """Base class holding shared ports."""

    def __init__(
        self,
        uow_factory: UowFactory,
        clock: Clock,
        bus: EventBus,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._bus = bus

    def _settings(self, uow: UnitOfWork) -> dict[str, str]:
        return uow.settings.get_all()

    def _commit(self, uow: UnitOfWork, *events: NetworkEvent) -> None:
        uow.commit()
        for event in events:
            self._bus.publish(event)
