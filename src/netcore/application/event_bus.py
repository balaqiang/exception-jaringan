"""Synchronous in-process event bus (DEC-013)."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress

from netcore.domain.enums import EventCategory
from netcore.domain.events import NetworkEvent

Handler = Callable[[NetworkEvent], None]
Unsubscribe = Callable[[], None]

logger = logging.getLogger("netcore.event_bus")


class EventBus:
    """Minimal pub/sub; handler errors never break the publisher."""

    def __init__(self) -> None:
        self._handlers: dict[EventCategory | None, list[Handler]] = defaultdict(list)

    def subscribe(
        self, category: EventCategory | None, handler: Handler
    ) -> Unsubscribe:
        """Subscribe to one category (or all when ``None``)."""
        self._handlers[category].append(handler)

        def unsubscribe() -> None:
            with suppress(ValueError):
                self._handlers[category].remove(handler)

        return unsubscribe

    def publish(self, event: NetworkEvent) -> None:
        """Deliver an event to matching handlers."""
        handlers = [
            *self._handlers.get(None, ()),
            *self._handlers.get(event.category, ()),
        ]
        for handler in tuple(handlers):
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler failed for %s", event.category)
