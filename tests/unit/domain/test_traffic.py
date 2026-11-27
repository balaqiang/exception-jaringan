"""NETWORK_SPEC §10 traffic model."""

from __future__ import annotations

from netcore.domain.enums import DropReason, Protocol
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.traffic import TrafficFlow, TrafficGenerator


def test_flow_utilization_and_capacity_immutability(two_router_lab) -> None:
    source = two_router_lab.require_device("srv-a")
    generator = TrafficGenerator()
    flow = TrafficFlow(
        src_device_id=source.id,
        dst_ip="10.0.2.10",
        protocol=Protocol.TCP,
        packet_size=512,
        packets_per_second=1000,
        duration_s=10,
    )
    report = generator.run(flow, two_router_lab, ForwardingEngine(two_router_lab))
    assert report.delivered
    assert report.load_mbps == 4.096
    assert report.utilization_pct == 0.4
    assert len(report.link_ids) == 5
    assert all(link.capacity_mbps == 1000 for link in two_router_lab.links())


def test_congestion_drops(two_router_lab) -> None:
    source = two_router_lab.require_device("srv-a")
    flow = TrafficFlow(
        src_device_id=source.id,
        dst_ip="10.0.2.10",
        protocol=Protocol.UDP,
        packet_size=9000,
        packets_per_second=100_000,
        duration_s=1,
    )
    report = TrafficGenerator().run(
        flow, two_router_lab, ForwardingEngine(two_router_lab)
    )
    assert report.utilization_pct == 100.0
    assert report.dropped_packets > 0
    assert report.drop_reason is DropReason.CONGESTION
