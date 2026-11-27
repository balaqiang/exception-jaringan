"""Simulated traffic model (NETWORK_SPEC §10)."""

from __future__ import annotations

from dataclasses import dataclass

from netcore.domain.enums import DropReason, Protocol
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.result import PacketRequest
from netcore.domain.topology import NetworkTopology


@dataclass(frozen=True, slots=True)
class TrafficFlow:
    """One simulated traffic flow."""

    src_device_id: int
    dst_ip: str
    protocol: Protocol = Protocol.TCP
    packet_size: int = 512
    packets_per_second: int = 100
    duration_s: int = 30
    seed: int = 42


@dataclass(frozen=True, slots=True)
class FlowReport:
    """Path, load and drop accounting for one flow."""

    flow: TrafficFlow
    delivered: bool
    path: tuple[int, ...]
    link_ids: tuple[int, ...]
    load_mbps: float
    utilization_pct: float
    packets: int
    bytes: int
    dropped_packets: int
    drop_reason: DropReason | None


class TrafficGenerator:
    """Account a representative packet over every link on its path."""

    def run(
        self,
        flow: TrafficFlow,
        topology: NetworkTopology,
        engine: ForwardingEngine,
    ) -> FlowReport:
        """Simulate one packet and scale it to the flow volume."""
        result = engine.simulate(
            PacketRequest(
                src_device_id=flow.src_device_id,
                dst_ip=flow.dst_ip,
                protocol=flow.protocol,
                size_bytes=min(9000, max(64, flow.packet_size)),
                payload="traffic",
            )
        )
        link_ids: list[int] = []
        for left, right in zip(result.path, result.path[1:], strict=False):
            for link in topology.links():
                ids = {link.endpoint_a.device_id, link.endpoint_b.device_id}
                if ids == {left, right} and link.id not in link_ids:
                    link_ids.append(link.id)
        packets = max(1, flow.packets_per_second * flow.duration_s)
        total_bytes = packets * flow.packet_size
        load_mbps = round(flow.packets_per_second * flow.packet_size * 8 / 1_000_000, 3)
        capacities = [topology.get_link(link_id).capacity_mbps for link_id in link_ids]
        utilization = 0.0
        dropped = 0
        if capacities:
            utilization = round(
                min(100.0, load_mbps / max(1, min(capacities)) * 100.0), 1
            )
            if load_mbps > min(capacities):
                excess = 1 - (min(capacities) / load_mbps)
                dropped = int(packets * excess)
        return FlowReport(
            flow=flow,
            delivered=result.delivered,
            path=result.path,
            link_ids=tuple(link_ids),
            load_mbps=load_mbps,
            utilization_pct=utilization,
            packets=packets,
            bytes=total_bytes,
            dropped_packets=dropped,
            drop_reason=DropReason.CONGESTION if dropped else result.drop_reason,
        )
