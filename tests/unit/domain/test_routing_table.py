"""AT-06 longest-prefix match."""

from __future__ import annotations

import ipaddress

import pytest

from netcore.domain.devices.router import RoutingEntry, RoutingTable
from netcore.domain.enums import RouteType
from netcore.domain.errors import DuplicateRouteError


def build_table() -> RoutingTable:
    table = RoutingTable()
    rows = [
        ("0.0.0.0/0", "10.0.0.1", "ge0/0", 1),
        ("10.0.0.0/8", "10.0.0.2", "ge0/1", 1),
        ("10.1.0.0/16", "10.0.0.3", "ge0/1", 1),
        ("10.1.2.0/24", None, "ge0/2", 0),
    ]
    for destination, next_hop, interface, distance in rows:
        table.add(
            RoutingEntry(
                id=len(table.entries()) + 1,
                destination=ipaddress.IPv4Network(destination),
                next_hop=(ipaddress.IPv4Address(next_hop) if next_hop else None),
                interface=interface,
                route_type=(
                    RouteType.CONNECTED if next_hop is None else RouteType.STATIC
                ),
                admin_distance=distance,
            )
        )
    return table


@pytest.mark.parametrize(
    ("dst", "expected"),
    [
        ("10.1.2.5", "10.1.2.0/24"),
        ("10.1.3.5", "10.1.0.0/16"),
        ("10.9.9.9", "10.0.0.0/8"),
        ("8.8.8.8", "0.0.0.0/0"),
        ("10.1.2.0", "10.1.2.0/24"),
    ],
)
def test_reference_lpm_table(dst: str, expected: str) -> None:
    route = build_table().longest_prefix_match(ipaddress.IPv4Address(dst))
    assert route is not None
    assert str(route.destination) == expected


def test_tie_break_admin_distance_metric_and_order() -> None:
    table = RoutingTable()
    destination = ipaddress.IPv4Network("10.5.0.0/16")
    table.add(
        RoutingEntry(1, destination, ipaddress.IPv4Address("10.0.0.1"), "a", metric=5)
    )
    table.add(
        RoutingEntry(
            2,
            destination,
            ipaddress.IPv4Address("10.0.0.2"),
            "b",
            admin_distance=0,
            metric=50,
        )
    )
    table.add(
        RoutingEntry(3, destination, ipaddress.IPv4Address("10.0.0.3"), "c", metric=1)
    )
    match = table.longest_prefix_match(ipaddress.IPv4Address("10.5.1.1"))
    assert match is not None
    assert match.id == 2


def test_duplicate_route_rejected() -> None:
    table = build_table()
    with pytest.raises(DuplicateRouteError):
        table.add(
            RoutingEntry(
                id=99,
                destination=ipaddress.IPv4Network("10.0.0.0/8"),
                next_hop=ipaddress.IPv4Address("10.0.0.2"),
                interface="ge0/1",
            )
        )
