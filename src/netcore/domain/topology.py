"""NetworkTopology aggregate root."""

from __future__ import annotations

import ipaddress
from collections import deque
from dataclasses import dataclass

from netcore.domain.addressing import MacAddress, parse_interface
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch
from netcore.domain.enums import DeviceStatus, RouteType
from netcore.domain.errors import (
    AddressNotInSubnetError,
    DeviceNotFoundError,
    DuplicateAddressError,
    DuplicateHostnameError,
    DuplicateMacError,
    InterfaceInUseError,
    InvalidLinkError,
    LinkNotFoundError,
    OverlappingSubnetError,
    ReservedAddressError,
    SubnetNotFoundError,
)
from netcore.domain.interface import NetworkInterface
from netcore.domain.link import InterfaceRef, Link
from netcore.domain.logging_mixin import LoggerMixin
from netcore.domain.subnet import Subnet


@dataclass(frozen=True, slots=True)
class RemovalReport:
    """What was removed together with a device."""

    device_name: str
    links: tuple[int, ...] = ()
    routes: int = 0
    interfaces: int = 0


@dataclass(slots=True)
class TopologyStats:
    """Cheap aggregate counters."""

    routers: int = 0
    switches: int = 0
    servers: int = 0
    links_up: int = 0
    links_down: int = 0

    def as_dict(self) -> dict[str, int]:
        """Return counters as a mapping."""
        return {
            "routers": self.routers,
            "switches": self.switches,
            "servers": self.servers,
            "links_up": self.links_up,
            "links_down": self.links_down,
        }


class NetworkTopology(LoggerMixin):
    """Aggregate root for devices, links and subnets (DEC-008)."""

    def __init__(self, name: str = "lab") -> None:
        self.name = name
        self._devices: dict[int, NetworkDevice] = {}
        self._links: dict[int, Link] = {}
        self._subnets: dict[int, Subnet] = {}
        self._next_device_id = 1
        self._next_link_id = 1
        self._next_subnet_id = 1
        self._next_route_id = 1
        self._next_frame_id = 1
        self._next_packet_id = 1

    # ------------------------------------------------------------------ ids
    def next_frame_id(self) -> int:
        """Monotonic frame id."""
        value = self._next_frame_id
        self._next_frame_id += 1
        return value

    def next_packet_id(self) -> int:
        """Monotonic packet id."""
        value = self._next_packet_id
        self._next_packet_id += 1
        return value

    def next_route_id(self) -> int:
        """Monotonic route id."""
        value = self._next_route_id
        self._next_route_id += 1
        return value

    def seed_counters(self, *, device: int, link: int, subnet: int, route: int) -> None:
        """Advance id counters after loading persisted data."""
        self._next_device_id = max(self._next_device_id, device)
        self._next_link_id = max(self._next_link_id, link)
        self._next_subnet_id = max(self._next_subnet_id, subnet)
        self._next_route_id = max(self._next_route_id, route)

    # --------------------------------------------------------------- devices
    def add_device(self, device: NetworkDevice) -> int:
        """Add a device enforcing lab-wide uniqueness."""
        lowered = device.hostname.lower()
        for existing in self._devices.values():
            if existing.hostname.lower() == lowered:
                raise DuplicateHostnameError(
                    f'Hostname "{device.hostname}" already exists.'
                )
            for iface in existing.interfaces():
                for candidate in device.interfaces():
                    if iface.mac == candidate.mac:
                        raise DuplicateMacError(
                            f"{candidate.mac} is already used by "
                            f"{existing.hostname} {iface.name}."
                        )
                    if (
                        iface.ip is not None
                        and candidate.ip is not None
                        and iface.ip == candidate.ip
                    ):
                        raise DuplicateAddressError(
                            f"{candidate.ip} is already assigned to "
                            f"{existing.hostname} {iface.name}."
                        )
        if device.id <= 0:
            device.id = self._next_device_id
        self._next_device_id = max(self._next_device_id, device.id + 1)
        self._devices[device.id] = device
        if isinstance(device, Router):
            device.sync_connected()
        return device.id

    def remove_device(self, device_id: int) -> RemovalReport:
        """Remove a device plus its links."""
        device = self.get_device(device_id)
        removed_links: list[int] = []
        for link in list(self._links.values()):
            if device_id in (link.endpoint_a.device_id, link.endpoint_b.device_id):
                removed_links.append(link.id)
                self.disconnect(link.id)
        routes = 0
        if isinstance(device, Router):
            routes = len(device.routing_table.entries())
        del self._devices[device_id]
        # Remove static routes whose next hop no longer exists in the lab.
        for router in self.routers():
            for entry in list(router.routing_table.entries()):
                if entry.route_type is not RouteType.STATIC:
                    continue
                if entry.next_hop is None:
                    continue
                if self.find_interface_by_ip(entry.next_hop) is None:
                    router.routing_table.remove(entry.id)
                    routes += 1
        return RemovalReport(
            device_name=device.hostname,
            links=tuple(removed_links),
            routes=routes,
            interfaces=len(device.interfaces()),
        )

    def get_device(self, device_id: int) -> NetworkDevice:
        """Return a device or raise ``DeviceNotFoundError``."""
        try:
            return self._devices[device_id]
        except KeyError as exc:
            raise DeviceNotFoundError(f"Device {device_id} not found.") from exc

    def find_by_hostname(self, hostname: str) -> NetworkDevice | None:
        """Case-insensitive hostname lookup."""
        lowered = hostname.strip().lower()
        for device in self._devices.values():
            if device.hostname.lower() == lowered:
                return device
        return None

    def require_device(self, hostname: str) -> NetworkDevice:
        """Return a device by hostname or raise."""
        device = self.find_by_hostname(hostname)
        if device is None:
            raise DeviceNotFoundError(f'Device "{hostname}" not found.')
        return device

    def devices(self) -> tuple[NetworkDevice, ...]:
        """Return devices ordered by id."""
        return tuple(self._devices[key] for key in sorted(self._devices))

    def routers(self) -> tuple[Router, ...]:
        """Return routers."""
        return tuple(d for d in self.devices() if isinstance(d, Router))

    def switches(self) -> tuple[Switch, ...]:
        """Return switches."""
        return tuple(d for d in self.devices() if isinstance(d, Switch))

    def servers(self) -> tuple[Server, ...]:
        """Return servers."""
        return tuple(d for d in self.devices() if isinstance(d, Server))

    def stats(self) -> TopologyStats:
        """Return aggregate counters."""
        stats = TopologyStats(
            routers=len(self.routers()),
            switches=len(self.switches()),
            servers=len(self.servers()),
        )
        for link in self._links.values():
            if link.admin_up:
                stats.links_up += 1
            else:
                stats.links_down += 1
        return stats

    # --------------------------------------------------------------- subnets
    def add_subnet(self, subnet: Subnet) -> int:
        """Add a subnet rejecting undeclared overlap."""
        for existing in self._subnets.values():
            declared = (
                subnet.parent_id == existing.id or existing.parent_id == subnet.id
            )
            if existing.network.overlaps(subnet.network) and not declared:
                raise OverlappingSubnetError(
                    f"{subnet.network} overlaps {existing.network}."
                )
        if subnet.id <= 0:
            subnet.id = self._next_subnet_id
        self._next_subnet_id = max(self._next_subnet_id, subnet.id + 1)
        self._subnets[subnet.id] = subnet
        return subnet.id

    def subnets(self) -> tuple[Subnet, ...]:
        """Return subnets ordered by id."""
        return tuple(self._subnets[key] for key in sorted(self._subnets))

    def get_subnet(self, subnet_id: int) -> Subnet:
        """Return a subnet by id."""
        try:
            return self._subnets[subnet_id]
        except KeyError as exc:
            raise SubnetNotFoundError(f"Subnet {subnet_id} not found.") from exc

    def subnet_for(self, ip: ipaddress.IPv4Address) -> Subnet | None:
        """Return the most specific subnet containing ``ip``."""
        matches = [s for s in self._subnets.values() if ip in s.network]
        if not matches:
            return None
        return max(matches, key=lambda item: item.network.prefixlen)

    def assign_address(
        self, device_id: int, interface_name: str, address_text: str
    ) -> NetworkInterface:
        """Assign a validated address to an interface."""
        device = self.get_device(device_id)
        interface = device.get_interface(interface_name)
        address = parse_interface(address_text)
        subnet = self.subnet_for(address.ip)
        if subnet is None:
            raise AddressNotInSubnetError(
                f"{address.ip} is outside every configured subnet."
            )
        if subnet.is_reserved(address.ip):
            raise ReservedAddressError(
                f"{address.ip} is a reserved address of {subnet.network}."
            )
        for other in self._devices.values():
            for candidate in other.interfaces():
                if candidate.ip == address.ip and candidate is not interface:
                    raise DuplicateAddressError(
                        f"{address.ip} is already assigned to "
                        f"{other.hostname} {candidate.name}."
                    )
                if candidate.mac == interface.mac and candidate is not interface:
                    raise DuplicateMacError(
                        f"{interface.mac} is already used by "
                        f"{other.hostname} {candidate.name}."
                    )
        interface.assign_address(address)
        if isinstance(device, Router):
            device.sync_connected()
        return interface

    def release_address(self, device_id: int, interface_name: str) -> None:
        """Remove the address from an interface."""
        device = self.get_device(device_id)
        interface = device.get_interface(interface_name)
        interface.clear_address()
        if isinstance(device, Router):
            device.sync_connected()

    # ----------------------------------------------------------------- links
    def get_interface(self, ref: InterfaceRef) -> NetworkInterface:
        """Resolve an interface reference."""
        return self.get_device(ref.device_id).get_interface(ref.name)

    def connect(
        self,
        ref_a: InterfaceRef,
        ref_b: InterfaceRef,
        capacity_mbps: int = 1000,
        latency_ms: float = 0.1,
        link_id: int | None = None,
    ) -> Link:
        """Create a validated point-to-point link."""
        if ref_a.device_id == ref_b.device_id:
            raise InvalidLinkError("A link must connect two different devices.")
        if not 1 <= capacity_mbps <= 400_000:
            raise InvalidLinkError("Capacity must be 1..400000 Mbps.")
        iface_a = self.get_interface(ref_a)
        iface_b = self.get_interface(ref_b)
        if iface_a.link_id is not None:
            raise InterfaceInUseError(
                f"{ref_a.name} on {ref_a.device_id} is already linked."
            )
        if iface_b.link_id is not None:
            raise InterfaceInUseError(
                f"{ref_b.name} on {ref_b.device_id} is already linked."
            )
        assigned_id = (
            link_id if link_id is not None and link_id > 0 else self._next_link_id
        )
        link = Link(
            id=assigned_id,
            endpoint_a=ref_a,
            endpoint_b=ref_b,
            capacity_mbps=capacity_mbps,
            latency_ms=latency_ms,
        )
        self._next_link_id = max(self._next_link_id, assigned_id + 1)
        self._links[link.id] = link
        iface_a.link_id = link.id
        iface_b.link_id = link.id
        return link

    def disconnect(self, link_id: int) -> None:
        """Remove a link and clear endpoint references."""
        try:
            link = self._links.pop(link_id)
        except KeyError as exc:
            raise LinkNotFoundError(f"Link {link_id} not found.") from exc
        for ref in (link.endpoint_a, link.endpoint_b):
            device = self._devices.get(ref.device_id)
            if device is not None:
                interface = device._interfaces.get(ref.name)
                if interface is not None:
                    interface.link_id = None

    def links(self) -> tuple[Link, ...]:
        """Return links ordered by id."""
        return tuple(self._links[key] for key in sorted(self._links))

    def get_link(self, link_id: int) -> Link:
        """Return a link by id."""
        try:
            return self._links[link_id]
        except KeyError as exc:
            raise LinkNotFoundError(f"Link {link_id} not found.") from exc

    def peer(self, ref: InterfaceRef) -> InterfaceRef | None:
        """Return the opposite endpoint, if linked."""
        link_id = self.get_interface(ref).link_id
        if link_id is None:
            return None
        return self._links[link_id].peer_of(ref)

    def link_for(self, ref: InterfaceRef) -> Link | None:
        """Return the link attached to an interface."""
        link_id = self.get_interface(ref).link_id
        return self._links.get(link_id) if link_id is not None else None

    def is_operational(self, ref: InterfaceRef) -> bool:
        """NETWORK_SPEC §3.1 interface operational state."""
        try:
            device = self.get_device(ref.device_id)
            interface = device.get_interface(ref.name)
        except Exception:
            return False
        if device.status is not DeviceStatus.ONLINE or not interface.admin_up:
            return False
        if interface.link_id is None:
            return False
        link = self._links.get(interface.link_id)
        if link is None or not link.admin_up:
            return False
        peer_ref = link.peer_of(ref)
        peer_device = self._devices.get(peer_ref.device_id)
        if peer_device is None or peer_device.status is not DeviceStatus.ONLINE:
            return False
        peer_interface = peer_device._interfaces.get(peer_ref.name)
        return peer_interface is not None and peer_interface.admin_up

    def l2_segment(self, ref: InterfaceRef) -> frozenset[InterfaceRef]:
        """Return all interfaces reachable at L2 without crossing routers."""
        seen: set[InterfaceRef] = {ref}
        queue: deque[InterfaceRef] = deque([ref])
        while queue:
            current = queue.popleft()
            try:
                peer = self.peer(current)
            except Exception:
                continue
            if peer is None or peer in seen:
                continue
            seen.add(peer)
            peer_device = self._devices.get(peer.device_id)
            if not isinstance(peer_device, Switch):
                continue
            for interface in peer_device.interfaces():
                if interface.link_id is None:
                    continue
                candidate = InterfaceRef(peer_device.id, interface.name)
                if candidate not in seen:
                    queue.append(candidate)
        return frozenset(seen)

    def l2_port_towards(self, switch: Switch, target_device_id: int) -> str | None:
        """Return the first switch port name on the L2 path to a device."""
        visited = {switch.id}
        queue: deque[tuple[int, str | None]] = deque([(switch.id, None)])
        while queue:
            device_id, first_port = queue.popleft()
            device = self._devices.get(device_id)
            if device is None:
                continue
            for interface in device.interfaces():
                if interface.link_id is None:
                    continue
                link = self._links.get(interface.link_id)
                if link is None:
                    continue
                ref = InterfaceRef(device_id, interface.name)
                peer = link.peer_of(ref)
                branch = first_port or interface.name
                if peer.device_id == target_device_id:
                    return branch
                peer_device = self._devices.get(peer.device_id)
                if isinstance(peer_device, Switch) and peer.device_id not in visited:
                    visited.add(peer.device_id)
                    queue.append((peer.device_id, branch))
        return None

    # ------------------------------------------------------------- lookups
    def find_interface_by_mac(
        self, mac: MacAddress
    ) -> tuple[NetworkDevice, NetworkInterface] | None:
        """Find the interface owning a MAC."""
        for device in self._devices.values():
            for interface in device.interfaces():
                if interface.mac == mac:
                    return device, interface
        return None

    def find_interface_by_ip(
        self, ip: ipaddress.IPv4Address
    ) -> tuple[NetworkDevice, NetworkInterface] | None:
        """Find the interface owning an IP."""
        for device in self._devices.values():
            for interface in device.interfaces():
                if interface.ip == ip:
                    return device, interface
        return None

    def addressed_interfaces(
        self,
    ) -> tuple[tuple[NetworkDevice, NetworkInterface], ...]:
        """Return every addressed interface with its device."""
        result: list[tuple[NetworkDevice, NetworkInterface]] = []
        for device in self.devices():
            for interface in device.interfaces():
                if interface.address is not None:
                    result.append((device, interface))
        return tuple(result)

    def gateway_for(
        self, device: Server, egress: NetworkInterface
    ) -> ipaddress.IPv4Address | None:
        """Return the configured gateway when it belongs to the egress subnet."""
        gateway = device.default_gateway
        if gateway is None or egress.address is None:
            return None
        if gateway in egress.address.network:
            return gateway
        return None


__all__ = ["NetworkTopology", "RemovalReport", "TopologyStats"]
