"""Audit event query and export use cases."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from netcore.application.dto import EventDTO, EventFilterDTO, ExportResultDTO
from netcore.application.services.base import (
    ServiceBase,
    event_dto,
    maps_errors,
    setting,
)


class EventLogService(ServiceBase):
    """Query and export the audit trail."""

    @maps_errors
    def query(self, request: EventFilterDTO) -> tuple[EventDTO, ...]:
        """Return filtered events newest first."""
        with self._uow() as uow:
            keep = setting(self._settings(uow), "event_retention", 1000)
            uow.events.prune(keep)
            uow.commit()
            topology = uow.topology.load()
            names = {device.id: device.hostname for device in topology.devices()}
            events = uow.events.query(
                severity=request.severity,
                category=request.category,
                device_id=request.device_id,
                search=request.search,
                limit=request.limit,
            )
            return tuple(
                event_dto(event, names.get(event.device_id or -1)) for event in events
            )

    @maps_errors
    def export(self, request: EventFilterDTO, fmt: str, path: str) -> ExportResultDTO:
        """Export filtered events as CSV or JSON (stdlib writers only)."""
        fmt = fmt.lower()
        if fmt not in {"csv", "json"}:
            from netcore.application.errors import ApplicationError

            raise ApplicationError("APP400", "Export format must be csv or json.")
        target = Path(path).expanduser()
        if target.suffix.lower() != f".{fmt}":
            target = target.with_suffix(f".{fmt}")
        target.parent.mkdir(parents=True, exist_ok=True)
        events = self.query(request)
        if fmt == "csv":
            with target.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "timestamp",
                        "severity",
                        "category",
                        "device",
                        "message",
                        "payload",
                    ]
                )
                for event in events:
                    writer.writerow(
                        [
                            event.timestamp,
                            event.severity,
                            event.category,
                            event.device_name or "",
                            event.message,
                            event.payload_json,
                        ]
                    )
        else:
            payload = [
                {
                    "timestamp": event.timestamp,
                    "severity": event.severity,
                    "category": event.category,
                    "device": event.device_name,
                    "message": event.message,
                    "payload": json.loads(event.payload_json or "{}"),
                }
                for event in events
            ]
            target.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        return ExportResultDTO(path=str(target), fmt=fmt, rows=len(events))
