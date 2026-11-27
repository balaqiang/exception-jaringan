"""Switch port and MAC table use cases."""

from __future__ import annotations

from netcore.application.dto import (
    DeviceDTO,
    MacEntryDTO,
    SwitchPortDTO,
)
from netcore.application.errors import ApplicationError
from netcore.application.services.base import ServiceBase, make_event, maps_errors
from netcore.application.services.mappers import device_dto
from netcore.domain.devices.switch import Switch
from netcore.domain.enums import EventCategory, Severity


class SwitchService(ServiceBase):
    """Port administration and MAC table operations."""

    @maps_errors
    def switches(self) -> tuple[DeviceDTO, ...]:
        """List switches."""
        with self._uow() as uow:
            topology = uow.topology.load()
            return tuple(device_dto(device) for device in topology.switches())

    @maps_errors
    def ports(self, switch_id: int) -> tuple[SwitchPortDTO, ...]:
        """List ports with peer and MAC count."""
        with self._uow() as uow:
            topology = uow.topology.load()
            switch = topology.get_device(switch_id)
            if not isinstance(switch, Switch):
                raise ApplicationError("APP400", "Selected device is not a switch.")
            entries = switch.mac_table.entries(self._clock.now())
            counts: dict[int, int] = {}
            for entry in entries:
                counts[entry.port] = counts.get(entry.port, 0) + 1
            result = []
            for port in switch.ports():
                peer = None
                if port.interface.link_id is not None:
                    from netcore.domain.link import InterfaceRef

                    peer_ref = topology.peer(
                        InterfaceRef(switch.id, port.interface.name)
                    )
                    if peer_ref is not None:
                        peer_device = topology.get_device(peer_ref.device_id)
                        peer = f"{peer_device.hostname}:{peer_ref.name}"
                result.append(
                    SwitchPortDTO(
                        switch_id=switch.id,
                        number=port.number,
                        admin_up=port.admin_up,
                        speed_mbps=port.speed_mbps,
                        description=port.description,
                        peer=peer,
                        mac_count=counts.get(port.number, 0),
                    )
                )
            return tuple(result)

    @maps_errors
    def set_port_admin(self, switch_id: int, number: int, up: bool) -> SwitchPortDTO:
        """Toggle a port's administrative state."""
        with self._uow() as uow:
            topology = uow.topology.load()
            switch = topology.get_device(switch_id)
            if not isinstance(switch, Switch):
                raise ApplicationError("APP400", "Selected device is not a switch.")
            switch.set_port_admin(number, up)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Port {number} on {switch.hostname} set {'up' if up else 'down'}.",
                device_id=switch.id,
            )
            uow.events.add(event)
            self._commit(uow, event)
            return self._port_dto(switch, number)

    @maps_errors
    def update_port(
        self,
        switch_id: int,
        number: int,
        *,
        speed_mbps: int | None = None,
        description: str | None = None,
    ) -> SwitchPortDTO:
        """Update speed or description of a port."""
        with self._uow() as uow:
            topology = uow.topology.load()
            switch = topology.get_device(switch_id)
            if not isinstance(switch, Switch):
                raise ApplicationError("APP400", "Selected device is not a switch.")
            switch.update_port(number, speed_mbps=speed_mbps, description=description)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Port {number} on {switch.hostname} updated.",
                device_id=switch.id,
            )
            uow.events.add(event)
            self._commit(uow, event)
            return self._port_dto(switch, number)

    @maps_errors
    def mac_table(self, switch_id: int) -> tuple[MacEntryDTO, ...]:
        """List non-expired MAC table entries."""
        with self._uow() as uow:
            topology = uow.topology.load()
            switch = topology.get_device(switch_id)
            if not isinstance(switch, Switch):
                raise ApplicationError("APP400", "Selected device is not a switch.")
            now = self._clock.now()
            return tuple(
                MacEntryDTO(
                    mac=entry.mac,
                    port=entry.port,
                    age_s=round((now - entry.learned_at).total_seconds(), 1),
                )
                for entry in switch.mac_table.entries(now)
            )

    @maps_errors
    def clear_mac_table(self, switch_id: int) -> None:
        """Clear the MAC table."""
        with self._uow() as uow:
            topology = uow.topology.load()
            switch = topology.get_device(switch_id)
            if not isinstance(switch, Switch):
                raise ApplicationError("APP400", "Selected device is not a switch.")
            switch.mac_table.clear()
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"MAC table on {switch.hostname} cleared.",
                device_id=switch.id,
            )
            uow.events.add(event)
            self._commit(uow, event)

    def _port_dto(self, switch: Switch, number: int) -> SwitchPortDTO:
        port = switch.get_port(number)
        peer = None
        if port.interface.link_id is not None:
            peer = f"link#{port.interface.link_id}"
        return SwitchPortDTO(
            switch_id=switch.id,
            number=port.number,
            admin_up=port.admin_up,
            speed_mbps=port.speed_mbps,
            description=port.description,
            peer=peer,
            mac_count=0,
        )
