"""AT-03/04/09/10 topology invariants."""

from __future__ import annotations

import ipaddress

import pytest

from netcore.application.labs import build_two_router_lab
from netcore.domain.addressing import MacAddress
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch
from netcore.domain.errors import (
    AddressNotInSubnetError,
    DuplicateAddressError,
    DuplicateHostnameError,
    DuplicateMacError,
    InterfaceInUseError,
    InvalidLinkError,
    InvalidPortError,
    OverlappingSubnetError,
    ReservedAddressError,
)
from netcore.domain.interface import NetworkInterface
from netcore.domain.link import InterfaceRef
from netcore.domain.subnet import Subnet


def test_duplicate_hostname_case_insensitive() -> None:
    topology = build_two_router_lab()
    duplicate = Server(
        "SRV-A",
        interfaces=[NetworkInterface("eth0", MacAddress("02:aa:00:00:00:01"))],
    )
    with pytest.raises(DuplicateHostnameError):
        topology.add_device(duplicate)


def test_duplicate_ip_and_mac() -> None:
    topology = build_two_router_lab()
    duplicate_ip = Server(
        "srv-c",
        interfaces=[
            NetworkInterface(
                "eth0",
                MacAddress("02:aa:00:00:00:02"),
                ipaddress.IPv4Interface("10.0.1.10/24"),
            )
        ],
    )
    with pytest.raises(DuplicateAddressError):
        topology.add_device(duplicate_ip)

    duplicate_mac = Server(
        "srv-d",
        interfaces=[
            NetworkInterface(
                "eth0",
                MacAddress("02:00:00:00:00:01"),
                ipaddress.IPv4Interface("10.0.1.99/24"),
            )
        ],
    )
    with pytest.raises(DuplicateMacError):
        topology.add_device(duplicate_mac)


def test_link_rules() -> None:
    topology = build_two_router_lab()
    r1 = topology.require_device("r1")
    with pytest.raises(InvalidLinkError):
        topology.connect(InterfaceRef(r1.id, "ge0/0"), InterfaceRef(r1.id, "ge0/1"))
    with pytest.raises(InterfaceInUseError):
        topology.connect(
            InterfaceRef(r1.id, "ge0/0"),
            InterfaceRef(topology.require_device("sw-a").id, "port2"),
        )


def test_switch_port_validation() -> None:
    switch = build_two_router_lab().require_device("sw-a")
    assert isinstance(switch, Switch)
    with pytest.raises(InvalidPortError):
        switch.get_port(99)


def test_assign_address_rules() -> None:
    topology = build_two_router_lab()
    router = topology.require_device("r1")
    with pytest.raises(ReservedAddressError):
        topology.assign_address(router.id, "ge0/1", "10.0.1.0/24")
    with pytest.raises(AddressNotInSubnetError):
        topology.assign_address(router.id, "ge0/1", "172.16.0.1/24")


def test_overlapping_subnet_rejected() -> None:
    topology = build_two_router_lab()
    with pytest.raises(OverlappingSubnetError):
        topology.add_subnet(
            Subnet(id=0, network=ipaddress.IPv4Network("10.0.1.128/25"))
        )


def test_remove_device_cleans_links() -> None:
    topology = build_two_router_lab()
    switch = topology.require_device("sw-a")
    report = topology.remove_device(switch.id)
    assert len(report.links) == 2
    assert all(
        switch.id not in (link.endpoint_a.device_id, link.endpoint_b.device_id)
        for link in topology.links()
    )


def test_remove_device_cleans_dependent_static_routes() -> None:
    topology = build_two_router_lab()
    r2 = topology.require_device("r2")
    routes_before = len(r2.routing_table.entries())
    report = topology.remove_device(topology.require_device("r1").id)
    assert report.routes >= 1
    assert len(r2.routing_table.entries()) < routes_before


def test_declared_parent_child_subnet_allowed() -> None:
    from netcore.domain.topology import NetworkTopology

    topology = NetworkTopology("nested")
    parent = Subnet(id=0, network=ipaddress.IPv4Network("10.0.0.0/16"))
    topology.add_subnet(parent)
    child = Subnet(
        id=0,
        network=ipaddress.IPv4Network("10.0.1.0/24"),
        parent_id=parent.id,
    )
    assert topology.add_subnet(child) == child.id


def test_l2_segment_stops_at_router() -> None:
    topology = build_two_router_lab()
    server = topology.require_device("srv-a")
    segment = topology.l2_segment(InterfaceRef(server.id, "eth0"))
    names = {(topology.get_device(ref.device_id).hostname, ref.name) for ref in segment}
    assert ("sw-a", "port1") in names
    assert ("r1", "ge0/1") in names
    assert ("r2", "ge0/0") not in names
