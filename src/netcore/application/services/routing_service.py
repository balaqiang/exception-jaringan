"""Routing table use cases."""

from __future__ import annotations

from netcore.application.dto import (
    DeviceDTO,
    RouteDTO,
    RouteLookupDTO,
    RouteRequest,
)
from netcore.application.errors import ApplicationError
from netcore.application.services.base import ServiceBase, make_event, maps_errors
from netcore.application.services.mappers import device_dto, route_dto
from netcore.domain.addressing import parse_ipv4, parse_network
from netcore.domain.devices.router import Router
from netcore.domain.enums import EventCategory, Severity


class RoutingService(ServiceBase):
    """Static routing configuration and LPM lookup."""

    @maps_errors
    def routers(self) -> tuple[DeviceDTO, ...]:
        """List routers available for selection."""
        with self._uow() as uow:
            topology = uow.topology.load()
            return tuple(device_dto(router) for router in topology.routers())

    @maps_errors
    def routes(self, router_id: int) -> tuple[RouteDTO, ...]:
        """List the routing table of one router."""
        with self._uow() as uow:
            topology = uow.topology.load()
            router = topology.get_device(router_id)
            if not isinstance(router, Router):
                raise ApplicationError("APP400", "Selected device is not a router.")
            return tuple(route_dto(route) for route in router.routing_table.entries())

    @maps_errors
    def add_static_route(self, request: RouteRequest) -> RouteDTO:
        """Validate and add a static/default route."""
        with self._uow() as uow:
            topology = uow.topology.load()
            router = topology.get_device(request.router_id)
            if not isinstance(router, Router):
                raise ApplicationError("APP400", "Selected device is not a router.")
            destination = parse_network(request.destination)
            next_hop = (
                parse_ipv4(request.next_hop) if request.next_hop.strip() else None
            )
            entry = router.add_static_route(
                destination,
                next_hop,
                request.interface,
                metric=request.metric,
                route_id=topology.next_route_id(),
            )
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Route {entry.destination} via {entry.next_hop} "
                f"{entry.interface} added to {router.hostname}.",
                device_id=router.id,
            )
            uow.events.add(event)
            self._commit(uow, event)
            return route_dto(entry)

    @maps_errors
    def remove_route(self, router_id: int, route_id: int) -> None:
        """Remove a static route."""
        with self._uow() as uow:
            topology = uow.topology.load()
            router = topology.get_device(router_id)
            if not isinstance(router, Router):
                raise ApplicationError("APP400", "Selected device is not a router.")
            router.routing_table.remove(route_id)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.WARNING,
                EventCategory.CONFIG,
                f"Route {route_id} removed from {router.hostname}.",
                device_id=router.id,
            )
            uow.events.add(event)
            self._commit(uow, event)

    @maps_errors
    def lookup(self, router_id: int, dst_ip: str) -> RouteLookupDTO:
        """Run a longest-prefix lookup."""
        with self._uow() as uow:
            topology = uow.topology.load()
            router = topology.get_device(router_id)
            if not isinstance(router, Router):
                raise ApplicationError("APP400", "Selected device is not a router.")
            destination = parse_ipv4(dst_ip)
            route = router.lookup(destination)
            if route is None:
                return RouteLookupDTO(
                    found=False,
                    message=f"No route to {destination} on {router.hostname}.",
                )
            return RouteLookupDTO(
                found=True,
                message=(
                    f"Matched {route.destination} (prefix "
                    f"/{route.destination.prefixlen}) via "
                    f"{route.next_hop or 'connected'} {route.interface}"
                ),
                destination=str(route.destination),
                next_hop=str(route.next_hop) if route.next_hop else None,
                interface=route.interface,
                prefix_len=route.destination.prefixlen,
            )


__all__ = ["RoutingService"]
