"""Deterministic packet forwarding engine (NETWORK_SPEC §6–§9)."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import UTC, datetime

from netcore.domain.addressing import MacAddress, parse_ipv4
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch
from netcore.domain.enums import (
    DeviceStatus,
    DropReason,
    HopKind,
    SimulationStatus,
)
from netcore.domain.errors import DeviceNotFoundError, InvalidSourceError
from netcore.domain.interface import NetworkInterface
from netcore.domain.link import InterfaceRef
from netcore.domain.packet import Frame, Packet
from netcore.domain.simulation.result import (
    HopRecord,
    PacketRequest,
    SimulationResult,
    TracerouteHop,
    TracerouteResult,
)
from netcore.domain.topology import NetworkTopology

PROCESSING_ROUTER_MS = 0.05
PROCESSING_SWITCH_MS = 0.01


@dataclass(slots=True)
class _Trace:
    topology: NetworkTopology
    now: datetime
    hops: list[HopRecord]
    path: list[int]
    latency_ms: float = 0.0
    max_hops: int = 64

    def record(
        self,
        device: NetworkDevice,
        kind: HopKind,
        *,
        ingress: str | None = None,
        egress: str | None = None,
        ttl_in: int | None = None,
        ttl_out: int | None = None,
        matched_route: str | None = None,
        reason: str = "",
    ) -> None:
        self.hops.append(
            HopRecord(
                index=len(self.hops),
                device_id=device.id,
                device_name=device.hostname,
                device_type=device.device_type,
                kind=kind,
                ingress=ingress,
                egress=egress,
                ttl_in=ttl_in,
                ttl_out=ttl_out,
                matched_route=matched_route,
                reason=reason,
            )
        )


class ForwardingEngine:
    """Walk a packet through the topology, recording every decision."""

    def __init__(
        self,
        topology: NetworkTopology,
        *,
        now: datetime | None = None,
        seed: int = 42,
        max_hops: int = 64,
    ) -> None:
        self._topology = topology
        self._now = now or datetime(2026, 1, 1, tzinfo=UTC)
        self._seed = seed
        self._max_hops = max_hops

    def simulate(self, request: PacketRequest) -> SimulationResult:
        """Simulate one packet end to end."""
        topology = self._topology
        try:
            source = topology.get_device(request.src_device_id)
        except DeviceNotFoundError as exc:
            raise InvalidSourceError(str(exc)) from exc
        if not isinstance(source, (Server, Router)) or not source.is_online():
            raise InvalidSourceError(f"Source {source.hostname} is not an online host.")
        if not source.addressed_interfaces():
            raise InvalidSourceError(f"Source {source.hostname} has no address.")

        dst_ip = parse_ipv4(request.dst_ip)
        packet = Packet(
            packet_id=topology.next_packet_id(),
            src_ip=self._source_ip(source, dst_ip),
            dst_ip=dst_ip,
            protocol=request.protocol,
            ttl=request.ttl,
            size_bytes=request.size_bytes,
            payload=request.payload,
        )
        trace = _Trace(
            topology=topology,
            now=self._now,
            hops=[],
            path=[source.id],
            max_hops=self._max_hops,
        )
        outcome = self._start(source, packet, trace)
        return self._finish(outcome, trace, request, dst_ip, packet)

    def _start(
        self, source: Server | Router, packet: Packet, trace: _Trace
    ) -> tuple[SimulationStatus, DropReason | None]:
        if isinstance(source, Server):
            egress, next_hop = self._server_egress(source, packet.dst_ip)
        else:
            egress, next_hop = self._router_egress(source, packet.dst_ip)
        if egress is None or next_hop is None:
            trace.record(
                source,
                HopKind.DROP,
                reason="No route and no usable gateway.",
            )
            return SimulationStatus.DROPPED, DropReason.NO_ROUTE

        trace.record(
            source,
            HopKind.SEND,
            egress=egress.name,
            ttl_in=packet.ttl,
            ttl_out=packet.ttl,
            reason=f"destination {packet.dst_ip} via {next_hop}",
        )
        mac, arp_owner = self._resolve_arp(source, egress, next_hop, trace)
        if mac is None:
            trace.record(
                source,
                HopKind.DROP,
                egress=egress.name,
                reason=f"ARP failed for {next_hop}.",
            )
            return SimulationStatus.DROPPED, DropReason.ARP_FAILED
        trace.record(
            arp_owner or source,
            HopKind.ARP,
            ingress=None if arp_owner is source else egress.name,
            reason=f"{next_hop} is-at {mac}",
        )

        peer = trace.topology.peer(InterfaceRef(source.id, egress.name))
        if peer is None:
            trace.record(
                source, HopKind.DROP, egress=egress.name, reason="Link missing."
            )
            return SimulationStatus.DROPPED, DropReason.LINK_DOWN
        link = trace.topology.link_for(InterfaceRef(source.id, egress.name))
        if link is None or not link.admin_up:
            trace.record(source, HopKind.DROP, egress=egress.name, reason="Link down.")
            return SimulationStatus.DROPPED, DropReason.LINK_DOWN
        trace.latency_ms += link.latency_ms
        frame = Frame(
            frame_id=trace.topology.next_frame_id(),
            src_mac=egress.mac,
            dst_mac=mac,
        )
        trace.path.append(peer.device_id)
        return self._walk(frame, packet, peer, trace)

    def _walk(
        self,
        frame: Frame,
        packet: Packet,
        here: InterfaceRef,
        trace: _Trace,
    ) -> tuple[SimulationStatus, DropReason | None]:
        for _ in range(trace.max_hops):
            device = trace.topology.get_device(here.device_id)
            if device.status is not DeviceStatus.ONLINE:
                trace.record(
                    device,
                    HopKind.DROP,
                    ingress=here.name,
                    reason="Device is offline.",
                )
                return SimulationStatus.DROPPED, DropReason.DEVICE_OFFLINE
            if len(trace.hops) > trace.max_hops:
                trace.record(device, HopKind.DROP, reason="Hop limit reached.")
                return SimulationStatus.DROPPED, DropReason.HOP_LIMIT

            if isinstance(device, Switch):
                next_ref, frame, drop = self._switch_step(device, frame, here, trace)
            elif isinstance(device, Router):
                next_ref, frame, packet, drop = self._router_step(
                    device, frame, packet, here, trace
                )
            elif isinstance(device, Server):
                next_ref, drop = None, self._server_step(device, packet, here, trace)
            else:  # pragma: no cover - defensive
                return SimulationStatus.DROPPED, DropReason.NOT_FOR_ME

            if drop is not None:
                return SimulationStatus.DROPPED, drop
            if next_ref is None:
                return SimulationStatus.DELIVERED, None
            link = trace.topology.link_for(here)
            if link is not None:
                trace.latency_ms += link.latency_ms
            trace.path.append(next_ref.device_id)
            here = next_ref

        last = trace.topology.get_device(here.device_id)
        trace.record(last, HopKind.DROP, reason="Hop limit reached.")
        return SimulationStatus.DROPPED, DropReason.HOP_LIMIT

    def _switch_step(
        self,
        switch: Switch,
        frame: Frame,
        here: InterfaceRef,
        trace: _Trace,
    ) -> tuple[InterfaceRef | None, Frame, DropReason | None]:
        ingress = switch.get_interface(here.name)
        if ingress.port_number is None:
            trace.record(switch, HopKind.DROP, ingress=here.name, reason="Not a port.")
            return None, frame, DropReason.PORT_DOWN
        if not ingress.admin_up:
            trace.record(
                switch, HopKind.DROP, ingress=here.name, reason="Ingress port down."
            )
            return None, frame, DropReason.PORT_DOWN
        switch.mac_table.learn(frame.src_mac, ingress.port_number, trace.now)

        port = switch.mac_table.lookup(frame.dst_mac, trace.now)
        if frame.is_broadcast() or port is None:
            owner = trace.topology.find_interface_by_mac(frame.dst_mac)
            egress_name: str | None = None
            if owner is not None and not frame.is_broadcast():
                egress_name = trace.topology.l2_port_towards(switch, owner[0].id)
            if egress_name is None:
                for candidate in switch.ports():
                    if candidate.number != ingress.port_number and candidate.admin_up:
                        egress_name = candidate.interface.name
                        break
            if egress_name is None:
                trace.record(
                    switch, HopKind.DROP, ingress=here.name, reason="No egress port."
                )
                return None, frame, DropReason.PORT_DOWN
            kind = HopKind.FLOOD
        else:
            egress_name = f"port{port}"
            kind = HopKind.SWITCH
            if port == ingress.port_number:
                trace.record(
                    switch,
                    HopKind.DROP,
                    ingress=here.name,
                    reason="Destination MAC is on ingress port (filtered).",
                )
                return None, frame, DropReason.FILTERED

        try:
            egress = switch.get_interface(egress_name)
        except Exception:
            trace.record(
                switch, HopKind.DROP, ingress=here.name, reason="Egress port missing."
            )
            return None, frame, DropReason.PORT_DOWN
        if not egress.admin_up:
            trace.record(
                switch,
                HopKind.DROP,
                ingress=here.name,
                egress=egress_name,
                reason="Egress port down.",
            )
            return None, frame, DropReason.PORT_DOWN
        peer = trace.topology.peer(InterfaceRef(switch.id, egress_name))
        if peer is None:
            trace.record(
                switch,
                HopKind.DROP,
                ingress=here.name,
                egress=egress_name,
                reason="Egress link missing.",
            )
            return None, frame, DropReason.LINK_DOWN
        link = trace.topology.link_for(InterfaceRef(switch.id, egress_name))
        if link is None or not link.admin_up:
            trace.record(
                switch,
                HopKind.DROP,
                ingress=here.name,
                egress=egress_name,
                reason="Egress link down.",
            )
            return None, frame, DropReason.LINK_DOWN
        trace.latency_ms += PROCESSING_SWITCH_MS
        trace.record(
            switch,
            kind,
            ingress=ingress.name,
            egress=egress_name,
            reason=f"{frame.src_mac} -> {frame.dst_mac}",
        )
        return peer, frame, None

    def _router_step(
        self,
        router: Router,
        frame: Frame,
        packet: Packet,
        here: InterfaceRef,
        trace: _Trace,
    ) -> tuple[InterfaceRef | None, Frame, Packet, DropReason | None]:
        ingress = router.get_interface(here.name)
        if packet.dst_ip in [iface.ip for iface in router.interfaces() if iface.ip]:
            trace.record(
                router,
                HopKind.DELIVER,
                ingress=ingress.name,
                ttl_in=packet.ttl,
                ttl_out=packet.ttl,
                reason="Destination is a local address.",
            )
            return None, frame, packet, None
        if packet.ttl - 1 <= 0:
            trace.record(
                router,
                HopKind.DROP,
                ingress=ingress.name,
                ttl_in=packet.ttl,
                ttl_out=0,
                reason="TTL expired.",
            )
            return None, frame, packet, DropReason.TTL_EXPIRED
        route = router.lookup(packet.dst_ip)
        if route is None:
            trace.record(
                router,
                HopKind.DROP,
                ingress=ingress.name,
                reason="No matching route.",
            )
            return None, frame, packet, DropReason.NO_ROUTE
        try:
            egress = router.get_interface(route.interface)
        except Exception:
            trace.record(
                router,
                HopKind.DROP,
                ingress=ingress.name,
                reason=f"Egress interface {route.interface} missing.",
            )
            return None, frame, packet, DropReason.INTERFACE_DOWN
        if not egress.admin_up:
            trace.record(
                router,
                HopKind.DROP,
                ingress=ingress.name,
                egress=route.interface,
                reason="Egress interface administratively down.",
            )
            return None, frame, packet, DropReason.INTERFACE_DOWN
        peer = trace.topology.peer(InterfaceRef(router.id, route.interface))
        if peer is None:
            trace.record(
                router,
                HopKind.DROP,
                ingress=ingress.name,
                egress=route.interface,
                reason="No link on egress interface.",
            )
            return None, frame, packet, DropReason.LINK_DOWN
        link = trace.topology.link_for(InterfaceRef(router.id, route.interface))
        if link is None or not link.admin_up:
            trace.record(
                router,
                HopKind.DROP,
                ingress=ingress.name,
                egress=route.interface,
                reason="Link is down.",
            )
            return None, frame, packet, DropReason.LINK_DOWN
        next_hop = route.next_hop or packet.dst_ip
        mac, arp_owner = self._resolve_arp(router, egress, next_hop, trace)
        if mac is None:
            trace.record(
                router,
                HopKind.DROP,
                ingress=ingress.name,
                egress=route.interface,
                reason=f"ARP failed for {next_hop}.",
            )
            return None, frame, packet, DropReason.ARP_FAILED
        ttl_out = packet.ttl - 1
        new_packet = packet.with_ttl(ttl_out)
        new_frame = Frame(
            frame_id=trace.topology.next_frame_id(),
            src_mac=egress.mac,
            dst_mac=mac,
        )
        trace.latency_ms += PROCESSING_ROUTER_MS
        trace.record(
            router,
            HopKind.ROUTE,
            ingress=ingress.name,
            egress=route.interface,
            ttl_in=packet.ttl,
            ttl_out=ttl_out,
            matched_route=route.label,
            reason=f"{route.destination} via {next_hop} {route.interface}",
        )
        trace.record(
            arp_owner or router,
            HopKind.ARP,
            ingress=None if arp_owner is router else route.interface,
            reason=f"{next_hop} is-at {mac}",
        )
        return peer, new_frame, new_packet, None

    def _server_step(
        self,
        server: Server,
        packet: Packet,
        here: InterfaceRef,
        trace: _Trace,
    ) -> DropReason | None:
        if server.owns_ip(packet.dst_ip):
            trace.record(
                server,
                HopKind.DELIVER,
                ingress=here.name,
                ttl_in=packet.ttl,
                ttl_out=packet.ttl,
                reason="Packet delivered to end host.",
            )
            return None
        trace.record(
            server,
            HopKind.DROP,
            ingress=here.name,
            reason="Packet not addressed to this server.",
        )
        return DropReason.NOT_FOR_ME

    def _server_egress(
        self, server: Server, dst_ip: ipaddress.IPv4Address
    ) -> tuple[NetworkInterface | None, ipaddress.IPv4Address | None]:
        for interface in server.addressed_interfaces():
            if interface.address is not None and dst_ip in interface.address.network:
                return interface, dst_ip
        if server.default_gateway is None:
            return None, None
        for interface in server.addressed_interfaces():
            if (
                interface.address is not None
                and server.default_gateway in interface.address.network
            ):
                return interface, server.default_gateway
        return None, None

    def _router_egress(
        self, router: Router, dst_ip: ipaddress.IPv4Address
    ) -> tuple[NetworkInterface | None, ipaddress.IPv4Address | None]:
        route = router.lookup(dst_ip)
        if route is None:
            return None, None
        try:
            interface = router.get_interface(route.interface)
        except Exception:
            return None, None
        return interface, route.next_hop or dst_ip

    def _source_ip(
        self, source: Server | Router, dst_ip: ipaddress.IPv4Address
    ) -> ipaddress.IPv4Address:
        for interface in source.addressed_interfaces():
            if interface.address is not None and dst_ip in interface.address.network:
                return interface.address.ip
        first = source.addressed_interfaces()[0]
        assert first.address is not None
        return first.address.ip

    def _resolve_arp(
        self,
        device: NetworkDevice,
        egress: NetworkInterface,
        target_ip: ipaddress.IPv4Address,
        trace: _Trace,
    ) -> tuple[MacAddress | None, NetworkDevice | None]:
        table = getattr(device, "arp_table", None)
        if table is not None:
            cached = table.get(target_ip, trace.now)
            if cached is not None:
                return cached, None
        segment = trace.topology.l2_segment(InterfaceRef(device.id, egress.name))
        for ref in segment:
            interface = trace.topology.get_interface(ref)
            if interface.ip != target_ip:
                continue
            owner = trace.topology.get_device(ref.device_id)
            if table is not None and egress.ip is not None:
                table.learn(target_ip, interface.mac, egress.name, trace.now)
            owner_table = getattr(owner, "arp_table", None)
            if owner_table is not None and egress.ip is not None:
                owner_table.learn(egress.ip, egress.mac, ref.name, trace.now)
            return interface.mac, owner
        return None, None

    def traceroute(self, request: PacketRequest) -> TracerouteResult:
        """Run TTL probes until delivery or the hop limit."""
        probes: list[TracerouteHop] = []
        for ttl in range(1, self._max_hops + 1):
            probe = PacketRequest(
                src_device_id=request.src_device_id,
                dst_ip=request.dst_ip,
                protocol=request.protocol,
                ttl=ttl,
                size_bytes=request.size_bytes,
                payload=request.payload,
            )
            result = self.simulate(probe)
            if result.status is SimulationStatus.DELIVERED:
                probes.append(TracerouteHop(ttl=ttl, router=None, status="DELIVERED"))
                return TracerouteResult(
                    hops=tuple(probes), delivered=True, dst_ip=str(request.dst_ip)
                )
            if result.drop_reason is DropReason.TTL_EXPIRED and result.hops:
                probes.append(
                    TracerouteHop(
                        ttl=ttl,
                        router=result.hops[-1].device_name,
                        status="TTL_EXPIRED",
                    )
                )
                continue
            probes.append(
                TracerouteHop(
                    ttl=ttl,
                    router=result.hops[-1].device_name if result.hops else None,
                    status=(result.drop_reason or DropReason.NO_ROUTE).value,
                )
            )
            break
        return TracerouteResult(
            hops=tuple(probes), delivered=False, dst_ip=str(request.dst_ip)
        )

    def _finish(
        self,
        outcome: tuple[SimulationStatus, DropReason | None],
        trace: _Trace,
        request: PacketRequest,
        dst_ip: ipaddress.IPv4Address,
        packet: Packet,
    ) -> SimulationResult:
        status, drop_reason = outcome
        return SimulationResult(
            run_id=0,
            status=status,
            drop_reason=drop_reason,
            hops=tuple(trace.hops),
            path=tuple(trace.path),
            total_latency_ms=round(trace.latency_ms, 4),
            started_at=trace.now,
            seed=self._seed,
            src_device_id=request.src_device_id,
            dst_ip=str(dst_ip),
            protocol=request.protocol,
            ttl=request.ttl,
            size_bytes=request.size_bytes,
            payload=request.payload,
        )
