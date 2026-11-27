"""AT-01, AT-05, AT-07, AT-08, AT-09 forwarding rules."""

from __future__ import annotations

import time

import pytest

from netcore.application.labs import build_spine_leaf_lab
from netcore.domain.enums import (
    DeviceStatus,
    DropReason,
    HopKind,
    SimulationStatus,
)
from netcore.domain.errors import InvalidSourceError
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.result import PacketRequest


def simulate(topo, dst: str = "10.0.2.10", **kwargs):
    server = topo.require_device("srv-a")
    kwargs.setdefault("ttl", 64)
    request = PacketRequest(
        src_device_id=server.id, dst_ip=dst, size_bytes=64, **kwargs
    )
    return ForwardingEngine(topo).simulate(request)


def test_at01_successful_delivery(two_router_lab) -> None:
    result = simulate(two_router_lab)
    assert result.status is SimulationStatus.DELIVERED
    assert result.drop_reason is None
    names = [two_router_lab.get_device(device_id).hostname for device_id in result.path]
    assert names == ["srv-a", "sw-a", "r1", "r2", "sw-b", "srv-b"]
    ttl_values = [hop.ttl_out for hop in result.hops if hop.ttl_out is not None]
    assert ttl_values[0] == 64
    assert ttl_values[-1] == 62
    assert 0 < result.total_latency_ms < 5
    assert any(hop.kind is HopKind.ARP for hop in result.hops)
    assert result.hops[-1].kind is HopKind.DELIVER


def test_at05_no_route(two_router_lab) -> None:
    result = simulate(two_router_lab, "172.16.0.9")
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.NO_ROUTE


def test_at07_ttl_expired(two_router_lab) -> None:
    result = simulate(two_router_lab, ttl=1)
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.TTL_EXPIRED
    assert result.hops[-1].device_name == "r1"


def test_at08_offline_device(two_router_lab) -> None:
    router = two_router_lab.require_device("r1")
    router.set_status(DeviceStatus.OFFLINE)
    result = simulate(two_router_lab)
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.DEVICE_OFFLINE


def test_at09_link_down(two_router_lab) -> None:
    link = two_router_lab.links()[2]
    link.admin_up = False
    result = simulate(two_router_lab)
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason in {DropReason.LINK_DOWN, DropReason.INTERFACE_DOWN}


def test_arp_does_not_consume_ttl(two_router_lab) -> None:
    result = simulate(two_router_lab)
    arp_hops = [hop for hop in result.hops if hop.kind is HopKind.ARP]
    assert arp_hops
    assert all(hop.ttl_in is None and hop.ttl_out is None for hop in arp_hops)


def test_traceroute(two_router_lab) -> None:
    server = two_router_lab.require_device("srv-a")
    result = ForwardingEngine(two_router_lab).traceroute(
        PacketRequest(src_device_id=server.id, dst_ip="10.0.2.10", ttl=1)
    )
    assert result.delivered
    assert result.hops[0].router == "r1"
    assert result.hops[-1].status == "DELIVERED"


def test_hop_limit(two_router_lab) -> None:
    server = two_router_lab.require_device("srv-a")
    result = ForwardingEngine(two_router_lab, max_hops=1).simulate(
        PacketRequest(src_device_id=server.id, dst_ip="10.0.2.10")
    )
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.HOP_LIMIT


def test_invalid_source(two_router_lab) -> None:
    switch = two_router_lab.require_device("sw-a")
    with pytest.raises(InvalidSourceError):
        ForwardingEngine(two_router_lab).simulate(
            PacketRequest(src_device_id=switch.id, dst_ip="10.0.2.10")
        )


def test_deterministic_and_fast(two_router_lab) -> None:
    start = time.perf_counter()
    first = simulate(two_router_lab)
    second = simulate(two_router_lab)
    elapsed = time.perf_counter() - start
    assert first.path == second.path
    assert first.hops[-1].ttl_out == second.hops[-1].ttl_out
    assert elapsed < 0.5


def test_spine_leaf_cross_leaf_delivery() -> None:
    topology = build_spine_leaf_lab()
    source = topology.require_device("srv-01")
    result = ForwardingEngine(topology).simulate(
        PacketRequest(src_device_id=source.id, dst_ip="10.10.4.12")
    )
    assert result.status is SimulationStatus.DELIVERED
    names = [topology.get_device(item).hostname for item in result.path]
    assert names[0] == "srv-01"
    assert names[-1] == "srv-08"
    assert "spine-1" in names
