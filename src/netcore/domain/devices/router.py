"""Router, routing entries and longest-prefix-match table."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, replace

from netcore.domain.addressing import MacAddress
from netcore.domain.arp import ArpTable
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.enums import DeviceType, RouteType
from netcore.domain.errors import (
    DuplicateRouteError,
    InvalidNextHopError,
    NotFoundError,
)
from netcore.domain.interface import NetworkInterface

PREFIX_ZERO = ipaddress.IPv4Network("0.0.0.0/0")


@dataclass(frozen=True, slots=True)
class RoutingEntry:
    """One route in a routing table."""

    id: int
    destination: ipaddress.IPv4Network
    next_hop: ipaddress.IPv4Address | None
    interface: str
    route_type: RouteType = RouteType.STATIC
    admin_distance: int = 1
    metric: int = 0
    insertion_index: int = 0

    @property
    def label(self) -> str:
        """Compact route description."""
        hop = str(self.next_hop) if self.next_hop else "connected"
        return f"{self.destination} via {hop} {self.interface}"


class RoutingTable:
    """Routing table with integer longest-prefix match (DEC-009)."""

    def __init__(self) -> None:
        self._entries: list[RoutingEntry] = []

    def entries(self) -> tuple[RoutingEntry, ...]:
        """Return entries in insertion order."""
        return tuple(self._entries)

    def add(self, entry: RoutingEntry) -> None:
        """Add an entry, rejecting duplicate destination/next-hop/interface."""
        for existing in self._entries:
            if (
                existing.destination == entry.destination
                and existing.next_hop == entry.next_hop
                and existing.interface == entry.interface
            ):
                raise DuplicateRouteError(
                    f"Route {entry.destination} via {entry.next_hop} already exists."
                )
        if entry.insertion_index == 0:
            entry = replace(entry, insertion_index=len(self._entries))
        self._entries.append(entry)

    def remove(self, entry_id: int) -> None:
        """Remove a route by id."""
        for index, entry in enumerate(self._entries):
            if entry.id == entry_id:
                del self._entries[index]
                return
        raise NotFoundError(f"Route {entry_id} not found.")

    def clear(self) -> None:
        """Remove all routes."""
        self._entries.clear()

    def sync_connected(self, interfaces: tuple[NetworkInterface, ...]) -> None:
        """Regenerate connected routes from addressed interfaces."""
        self._entries = [
            entry
            for entry in self._entries
            if entry.route_type is not RouteType.CONNECTED
        ]
        for interface in interfaces:
            if interface.address is None:
                continue
            self._entries.append(
                RoutingEntry(
                    id=0,
                    destination=interface.address.network,
                    next_hop=None,
                    interface=interface.name,
                    route_type=RouteType.CONNECTED,
                    admin_distance=0,
                    metric=0,
                    insertion_index=len(self._entries),
                )
            )

    def longest_prefix_match(self, dst: ipaddress.IPv4Address) -> RoutingEntry | None:
        """Return the best matching route, or None."""
        candidates = [entry for entry in self._entries if dst in entry.destination]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda entry: (
                entry.destination.prefixlen,
                -entry.admin_distance,
                -entry.metric,
                -entry.insertion_index,
            ),
        )


class Router(NetworkDevice):
    """L3 device that decrements TTL and forwards using LPM."""

    device_type = DeviceType.ROUTER

    def __init__(
        self,
        hostname: str,
        *,
        device_id: int = 0,
        interface_count: int = 4,
        interfaces: list[NetworkInterface] | None = None,
        location: str = "",
        description: str = "",
        arp_timeout_s: int = 300,
    ) -> None:
        self.routing_table = RoutingTable()
        self.arp_table = ArpTable(arp_timeout_s)
        super().__init__(
            hostname,
            device_id=device_id,
            location=location,
            description=description,
            interfaces=interfaces,
        )
        if interfaces is None:
            for index in range(interface_count):
                self.add_interface(
                    NetworkInterface(
                        name=f"ge0/{index}",
                        mac=MacAddress(f"02:00:00:00:00:{index + 1:02x}"),
                    )
                )

    def add_static_route(
        self,
        destination: ipaddress.IPv4Network,
        next_hop: ipaddress.IPv4Address | None,
        interface: str,
        *,
        metric: int = 0,
        route_id: int = 0,
    ) -> RoutingEntry:
        """Validate and add a static or default route."""
        self.get_interface(interface)
        if next_hop is not None:
            connected = [
                iface.address.network
                for iface in self.addressed_interfaces()
                if iface.address is not None
            ]
            if not any(next_hop in network for network in connected):
                raise InvalidNextHopError(
                    f"Next hop {next_hop} is not on a connected subnet of "
                    f"{self.hostname}."
                )
        route_type = (
            RouteType.DEFAULT if destination == PREFIX_ZERO else RouteType.STATIC
        )
        entry = RoutingEntry(
            id=route_id,
            destination=destination,
            next_hop=next_hop,
            interface=interface,
            route_type=route_type,
            admin_distance=1,
            metric=metric,
        )
        self.routing_table.add(entry)
        return self.routing_table.entries()[-1]

    def sync_connected(self) -> None:
        """Refresh connected routes after address changes."""
        self.routing_table.sync_connected(self.interfaces())

    def lookup(self, dst: ipaddress.IPv4Address) -> RoutingEntry | None:
        """Longest-prefix lookup."""
        return self.routing_table.longest_prefix_match(dst)

    def receive(self, *args: object, **kwargs: object) -> object:
        """Delegated to the forwarding engine."""
        raise NotImplementedError("Use ForwardingEngine to route packets")
