"""Sample lab factories (pure domain construction)."""

from __future__ import annotations

import ipaddress

from netcore.domain.addressing import MacAddress
from netcore.domain.devices.router import Router
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch
from netcore.domain.interface import NetworkInterface
from netcore.domain.link import InterfaceRef
from netcore.domain.subnet import Subnet
from netcore.domain.topology import NetworkTopology

_MAC_COUNTER = 0


def _mac() -> MacAddress:
    global _MAC_COUNTER  # noqa: PLW0603
    _MAC_COUNTER += 1
    value = _MAC_COUNTER
    return MacAddress(f"02:00:00:00:{value // 256:02x}:{value % 256:02x}")


def _reset_macs() -> None:
    global _MAC_COUNTER  # noqa: PLW0603
    _MAC_COUNTER = 0


def _iface(
    name: str,
    *,
    address: str | None = None,
    port: int | None = None,
    speed: int = 1000,
) -> NetworkInterface:
    return NetworkInterface(
        name=name,
        mac=_mac(),
        address=ipaddress.IPv4Interface(address) if address else None,
        port_number=port,
        speed_mbps=speed,
    )


def _add_subnet(topology: NetworkTopology, cidr: str, name: str, gateway: str) -> None:
    topology.add_subnet(
        Subnet(
            id=0,
            network=ipaddress.IPv4Network(cidr),
            name=name,
            gateway=ipaddress.IPv4Address(gateway),
        )
    )


def build_two_router_lab() -> NetworkTopology:
    """Reference lab from NETWORK_SPEC §13."""
    _reset_macs()
    topology = NetworkTopology("two-router")
    _add_subnet(topology, "10.0.1.0/24", "LAN-A", "10.0.1.1")
    _add_subnet(topology, "10.0.2.0/24", "LAN-B", "10.0.2.1")
    _add_subnet(topology, "10.0.12.0/30", "P2P-R1-R2", "10.0.12.1")

    srv_a = Server(
        "srv-a",
        interfaces=[_iface("eth0", address="10.0.1.10/24")],
        default_gateway=ipaddress.IPv4Address("10.0.1.1"),
    )
    sw_a = Switch(
        "sw-a",
        port_count=24,
        interfaces=[_iface(f"port{number}", port=number) for number in range(1, 25)],
    )
    r1 = Router(
        "r1",
        interfaces=[
            _iface("ge0/0", address="10.0.12.1/30"),
            _iface("ge0/1", address="10.0.1.1/24"),
        ],
    )
    r2 = Router(
        "r2",
        interfaces=[
            _iface("ge0/0", address="10.0.12.2/30"),
            _iface("ge0/1", address="10.0.2.1/24"),
        ],
    )
    sw_b = Switch(
        "sw-b",
        port_count=24,
        interfaces=[_iface(f"port{number}", port=number) for number in range(1, 25)],
    )
    srv_b = Server(
        "srv-b",
        interfaces=[_iface("eth0", address="10.0.2.10/24")],
        default_gateway=ipaddress.IPv4Address("10.0.2.1"),
    )

    for device in (srv_a, sw_a, r1, r2, sw_b, srv_b):
        topology.add_device(device)

    topology.connect(InterfaceRef(srv_a.id, "eth0"), InterfaceRef(sw_a.id, "port1"))
    topology.connect(InterfaceRef(sw_a.id, "port24"), InterfaceRef(r1.id, "ge0/1"))
    topology.connect(InterfaceRef(r1.id, "ge0/0"), InterfaceRef(r2.id, "ge0/0"))
    topology.connect(InterfaceRef(r2.id, "ge0/1"), InterfaceRef(sw_b.id, "port24"))
    topology.connect(InterfaceRef(sw_b.id, "port1"), InterfaceRef(srv_b.id, "eth0"))

    r1.add_static_route(
        ipaddress.IPv4Network("10.0.2.0/24"),
        ipaddress.IPv4Address("10.0.12.2"),
        "ge0/0",
        route_id=topology.next_route_id(),
    )
    r2.add_static_route(
        ipaddress.IPv4Network("10.0.1.0/24"),
        ipaddress.IPv4Address("10.0.12.1"),
        "ge0/0",
        route_id=topology.next_route_id(),
    )
    return topology


def build_spine_leaf_lab() -> NetworkTopology:
    """Two spines, four leaves and eight servers."""
    _reset_macs()
    topology = NetworkTopology("spine-leaf")
    for leaf in range(1, 5):
        _add_subnet(
            topology,
            f"10.10.{leaf}.0/24",
            f"leaf-{leaf}",
            f"10.10.{leaf}.1",
        )
    spines = [
        Router(
            f"spine-{index}",
            interfaces=[
                _iface(f"ge0/{leaf}", address=f"10.10.{leaf}.{index}/24")
                for leaf in range(1, 5)
            ],
        )
        for index in (1, 2)
    ]
    leaves = [
        Switch(
            f"leaf-{index}",
            port_count=24,
            interfaces=[_iface(f"port{n}", port=n) for n in range(1, 25)],
        )
        for index in range(1, 5)
    ]
    servers: list[Server] = []
    for leaf in range(1, 5):
        for offset in (1, 2):
            host = (leaf - 1) * 2 + offset
            servers.append(
                Server(
                    f"srv-{host:02d}",
                    interfaces=[
                        _iface("eth0", address=f"10.10.{leaf}.{10 + offset}/24")
                    ],
                    default_gateway=ipaddress.IPv4Address(f"10.10.{leaf}.1"),
                )
            )

    for device in [*spines, *leaves, *servers]:
        topology.add_device(device)

    for leaf_index, leaf in enumerate(leaves, start=1):
        for offset in (1, 2):
            server = servers[(leaf_index - 1) * 2 + offset - 1]
            topology.connect(
                InterfaceRef(server.id, "eth0"),
                InterfaceRef(leaf.id, f"port{offset}"),
            )
        for spine_index, spine in enumerate(spines, start=1):
            topology.connect(
                InterfaceRef(leaf.id, f"port{22 + spine_index}"),
                InterfaceRef(spine.id, f"ge0/{leaf_index}"),
            )
    return topology
