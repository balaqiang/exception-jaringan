"""Settings and lab lifecycle use cases."""

from __future__ import annotations

from netcore.application.dto import SettingsDTO, SettingsUpdateRequest
from netcore.application.errors import ApplicationError
from netcore.application.labs import build_spine_leaf_lab, build_two_router_lab
from netcore.application.services.base import (
    ServiceBase,
    make_event,
    maps_errors,
    setting,
)
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.topology import NetworkTopology


class SettingsService(ServiceBase):
    """Read/write settings and load sample labs."""

    def __init__(self, *args, db_path: str, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self._db_path = db_path

    @maps_errors
    def get(self) -> SettingsDTO:
        """Return effective settings."""
        with self._uow() as uow:
            values = self._settings(uow)
        return self._to_dto(values)

    def _to_dto(self, values: dict[str, str]) -> SettingsDTO:
        return SettingsDTO(
            default_ttl=setting(values, "default_ttl", 64),
            default_link_capacity=setting(values, "default_link_capacity", 1000),
            arp_timeout_s=setting(values, "arp_timeout_s", 300),
            mac_timeout_s=setting(values, "mac_timeout_s", 300),
            max_hops=setting(values, "max_hops", 64),
            event_retention=setting(values, "event_retention", 1000),
            seed=setting(values, "seed", 42),
            poll_interval_ms=setting(values, "poll_interval_ms", 500),
            db_path=self._db_path,
        )

    @maps_errors
    def update(self, request: SettingsUpdateRequest) -> SettingsDTO:
        """Validate and persist settings."""
        checks = [
            ("default_ttl", request.default_ttl, 1, 255),
            ("default_link_capacity", request.default_link_capacity, 1, 400_000),
            ("arp_timeout_s", request.arp_timeout_s, 10, 3600),
            ("mac_timeout_s", request.mac_timeout_s, 10, 3600),
            ("max_hops", request.max_hops, 8, 255),
            ("event_retention", request.event_retention, 10, 100_000),
            ("seed", request.seed, 0, 2_147_483_647),
            ("poll_interval_ms", request.poll_interval_ms, 100, 5000),
        ]
        for name, value, low, high in checks:
            if not low <= value <= high:
                raise ApplicationError(
                    "APP400", f"{name} must be between {low} and {high}."
                )
        values = {
            "default_ttl": str(request.default_ttl),
            "default_link_capacity": str(request.default_link_capacity),
            "arp_timeout_s": str(request.arp_timeout_s),
            "mac_timeout_s": str(request.mac_timeout_s),
            "max_hops": str(request.max_hops),
            "event_retention": str(request.event_retention),
            "seed": str(request.seed),
            "poll_interval_ms": str(request.poll_interval_ms),
        }
        with self._uow() as uow:
            uow.settings.update(values)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.SYSTEM,
                "Settings updated.",
                payload=values,
            )
            uow.events.add(event)
            self._commit(uow, event)
        return self._to_dto(values)

    @maps_errors
    def load_sample_lab(self, name: str) -> None:
        """Replace the lab with a bundled sample topology."""
        builders = {
            "two-router": build_two_router_lab,
            "spine-leaf": build_spine_leaf_lab,
        }
        builder = builders.get(name)
        if builder is None:
            raise ApplicationError("APP404", f"Unknown sample lab {name}.")
        with self._uow() as uow:
            topology = builder()
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.SYSTEM,
                f"Sample lab '{name}' loaded with {len(topology.devices())} devices.",
            )
            uow.events.add(event)
            self._commit(uow, event)

    @maps_errors
    def reset_lab(self) -> None:
        """Remove all devices, links and subnets."""
        with self._uow() as uow:
            topology = NetworkTopology("lab")
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.WARNING,
                EventCategory.SYSTEM,
                "Lab reset: all topology data removed.",
            )
            uow.events.add(event)
            self._commit(uow, event)
