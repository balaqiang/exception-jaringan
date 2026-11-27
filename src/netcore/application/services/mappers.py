"""Domain -> DTO mapping helpers."""

from __future__ import annotations

from netcore.application.dto import (
    DeviceDTO,
    HopDTO,
    InterfaceDTO,
    LinkDTO,
    RouteDTO,
    SimulationResultDTO,
    SubnetDTO,
    TopologyDTO,
    TopologyLinkDTO,
    TopologyNodeDTO,
)
from netcore.domain.devices.router import RoutingEntry
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch
from netcore.domain.interface import NetworkInterface
from netcore.domain.link import InterfaceRef, Link
from netcore.domain.simulation.result import HopRecord, SimulationResult
from netcore.domain.subnet import Subnet
from netcore.domain.topology import NetworkTopology


def device_dto(device) -> DeviceDTO:  # noqa: ANN001
    """Map any concrete device."""
    gateway = (
        str(device.default_gateway)
        if isinstance(device, Server) and device.default_gateway
        else None
    )
    port_count = device.port_count if isinstance(device, Switch) else None
    return DeviceDTO(
        device_id=device.id,
        hostname=device.hostname,
        device_type=device.device_type.value,
        status=device.status.value,
        interface_count=len(device.interfaces()),
        location=device.location,
        description=device.description,
        gateway=gateway,
        port_count=port_count,
    )


def interface_dto(
    topology: NetworkTopology,
    device,  # noqa: ANN001
    interface: NetworkInterface,
) -> InterfaceDTO:
    """Map an interface plus its peer label."""
    peer: str | None = None
    link = topology.link_for(InterfaceRef(device.id, interface.name))
    if link is not None:
        peer_ref = link.peer_of(InterfaceRef(device.id, interface.name))
        try:
            peer_device = topology.get_device(peer_ref.device_id)
            peer = f"{peer_device.hostname}:{peer_ref.name}"
        except Exception:
            peer = None
    return InterfaceDTO(
        device_id=device.id,
        device_name=device.hostname,
        name=interface.name,
        mac=interface.mac.value,
        ip=str(interface.address.ip) if interface.address else None,
        prefix_len=interface.address.network.prefixlen if interface.address else None,
        admin_up=interface.admin_up,
        peer=peer,
        port_number=interface.port_number,
        speed_mbps=interface.speed_mbps,
        description=interface.description,
    )


def link_dto(link: Link, topology: NetworkTopology) -> LinkDTO:
    """Map a link with endpoint labels."""
    labels: list[str] = []
    for ref in (link.endpoint_a, link.endpoint_b):
        try:
            device = topology.get_device(ref.device_id)
            labels.append(f"{device.hostname}:{ref.name}")
        except Exception:
            labels.append(f"#{ref.device_id}:{ref.name}")
    return LinkDTO(
        link_id=link.id,
        endpoint_a=labels[0],
        endpoint_b=labels[1],
        capacity_mbps=link.capacity_mbps,
        latency_ms=link.latency_ms,
        admin_up=link.admin_up,
    )


def subnet_dto(subnet: Subnet, used: int) -> SubnetDTO:
    """Map a subnet with capacity statistics."""
    total = subnet.usable_hosts()
    free = max(0, total - used)
    utilization = round(min(100.0, used / total * 100.0), 1) if total else 0.0
    return SubnetDTO(
        subnet_id=subnet.id,
        cidr=subnet.cidr,
        name=subnet.name,
        gateway=str(subnet.gateway) if subnet.gateway else None,
        total_hosts=total,
        used_hosts=used,
        free_hosts=free,
        utilization_pct=utilization,
    )


def route_dto(route: RoutingEntry) -> RouteDTO:
    """Map a routing entry."""
    return RouteDTO(
        route_id=route.id,
        destination=str(route.destination),
        next_hop=str(route.next_hop) if route.next_hop else None,
        interface=route.interface,
        route_type=route.route_type.value,
        admin_distance=route.admin_distance,
        metric=route.metric,
    )


def hop_dto(hop: HopRecord) -> HopDTO:
    """Map a hop record."""
    return HopDTO(
        index=hop.index,
        device_id=hop.device_id,
        device_name=hop.device_name,
        device_type=hop.device_type.value,
        kind=hop.kind.value,
        ingress=hop.ingress,
        egress=hop.egress,
        ttl_in=hop.ttl_in,
        ttl_out=hop.ttl_out,
        matched_route=hop.matched_route,
        reason=hop.reason,
    )


def simulation_dto(
    result: SimulationResult, topology: NetworkTopology
) -> SimulationResultDTO:
    """Map a simulation result with resolved device names."""
    names: list[str] = []
    for device_id in result.path:
        try:
            names.append(topology.get_device(device_id).hostname)
        except Exception:
            names.append(f"#{device_id}")
    ttl_values = [hop.ttl_out for hop in result.hops if hop.ttl_out is not None]
    return SimulationResultDTO(
        run_id=result.run_id,
        status=result.status.value,
        drop_reason=result.drop_reason.value if result.drop_reason else None,
        hops=tuple(hop_dto(hop) for hop in result.hops),
        path_names=tuple(names),
        path_ids=tuple(result.path),
        total_latency_ms=round(result.total_latency_ms, 3),
        ttl_in=result.ttl,
        ttl_out=ttl_values[-1] if ttl_values else result.ttl,
        seed=result.seed,
        started_at=result.started_at.isoformat(timespec="seconds"),
    )


def topology_dto(topology: NetworkTopology, path: tuple[int, ...] = ()) -> TopologyDTO:
    """Map the whole topology for the canvas."""
    nodes = tuple(
        TopologyNodeDTO(
            device_id=device.id,
            hostname=device.hostname,
            device_type=device.device_type.value,
            status=device.status.value,
            interface_count=len(device.interfaces()),
        )
        for device in topology.devices()
    )
    links: list[TopologyLinkDTO] = []
    for link in topology.links():
        labels = []
        for ref in (link.endpoint_a, link.endpoint_b):
            try:
                device = topology.get_device(ref.device_id)
                labels.append(f"{device.hostname}:{ref.name}")
            except Exception:
                labels.append(f"#{ref.device_id}")
        links.append(
            TopologyLinkDTO(
                link_id=link.id,
                endpoint_a=labels[0],
                endpoint_b=labels[1],
                admin_up=link.admin_up,
                capacity_mbps=link.capacity_mbps,
            )
        )
    return TopologyDTO(
        name=topology.name,
        nodes=nodes,
        links=tuple(links),
        subnet_count=len(topology.subnets()),
        path=path,
    )


__all__ = [
    "device_dto",
    "hop_dto",
    "interface_dto",
    "link_dto",
    "route_dto",
    "simulation_dto",
    "subnet_dto",
    "topology_dto",
]
