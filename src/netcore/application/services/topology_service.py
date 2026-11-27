"""Topology and link use cases."""

from __future__ import annotations

from netcore.application.dto import ConnectRequest, LinkDTO, TopologyDTO
from netcore.application.services.base import ServiceBase, make_event, maps_errors
from netcore.application.services.mappers import link_dto, topology_dto
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.link import InterfaceRef


class TopologyService(ServiceBase):
    """Read the topology and manage links."""

    @maps_errors
    def snapshot(self, path: tuple[int, ...] = ()) -> TopologyDTO:
        """Return nodes and links for rendering."""
        with self._uow() as uow:
            return topology_dto(uow.topology.load(), path)

    @maps_errors
    def links(self) -> tuple[LinkDTO, ...]:
        """List links."""
        with self._uow() as uow:
            topology = uow.topology.load()
            return tuple(link_dto(link, topology) for link in topology.links())

    @maps_errors
    def connect(self, request: ConnectRequest) -> LinkDTO:
        """Create a link between two named interfaces."""
        with self._uow() as uow:
            topology = uow.topology.load()
            device_a = topology.require_device(request.device_a)
            device_b = topology.require_device(request.device_b)
            link = topology.connect(
                InterfaceRef(device_a.id, request.interface_a),
                InterfaceRef(device_b.id, request.interface_b),
                capacity_mbps=request.capacity_mbps,
            )
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Link {device_a.hostname}:{request.interface_a} <-> "
                f"{device_b.hostname}:{request.interface_b} created.",
            )
            uow.events.add(event)
            self._commit(uow, event)
            return link_dto(link, topology)

    @maps_errors
    def disconnect(self, link_id: int) -> None:
        """Delete a link."""
        with self._uow() as uow:
            topology = uow.topology.load()
            topology.disconnect(link_id)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.WARNING,
                EventCategory.CONFIG,
                f"Link {link_id} deleted.",
            )
            uow.events.add(event)
            self._commit(uow, event)

    @maps_errors
    def set_link_admin(self, link_id: int, up: bool) -> LinkDTO:
        """Toggle a link's administrative state."""
        with self._uow() as uow:
            topology = uow.topology.load()
            link = topology.get_link(link_id)
            link.admin_up = up
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO if up else Severity.WARNING,
                EventCategory.STATE,
                f"Link {link_id} set {'up' if up else 'down'}.",
            )
            uow.events.add(event)
            self._commit(uow, event)
            return link_dto(link, topology)
