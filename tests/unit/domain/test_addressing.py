"""AT-02/03/04 addressing rules."""

from __future__ import annotations

import ipaddress
import random

import pytest

from netcore.domain.addressing import (
    MacAddress,
    generate_mac,
    parse_interface,
    parse_ipv4,
    parse_network,
)
from netcore.domain.errors import InvalidAddressError
from netcore.domain.subnet import Subnet


@pytest.mark.parametrize(
    "value",
    ["10.0.0.1", "192.168.10.254", "0.0.0.0", "255.255.255.255"],
)
def test_valid_ipv4(value: str) -> None:
    assert str(parse_ipv4(value)) == value


@pytest.mark.parametrize(
    "value",
    ["10.0.0.256", "10.0.0", "10.0.0.1.2", "010.0.0.1", " 10.0.0.1", "", "a.b.c.d"],
)
def test_invalid_ipv4(value: str) -> None:
    with pytest.raises(InvalidAddressError):
        parse_ipv4(value)


def test_interface_and_network_parsing() -> None:
    assert parse_interface("10.0.1.10/24").ip == ipaddress.IPv4Address("10.0.1.10")
    with pytest.raises(InvalidAddressError):
        parse_interface("10.0.1.10")
    assert str(parse_network("10.1.0.0/16")) == "10.1.0.0/16"
    with pytest.raises(InvalidAddressError):
        parse_network("10.1.2.5/16")


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("AA:BB:CC:DD:EE:01", "aa:bb:cc:dd:ee:01"),
        ("aa-bb-cc-dd-ee-01", "aa:bb:cc:dd:ee:01"),
        ("aabb.ccdd.ee01", "aa:bb:cc:dd:ee:01"),
        ("aabbccddee01", "aa:bb:cc:dd:ee:01"),
    ],
)
def test_mac_normalisation(text: str, canonical: str) -> None:
    assert MacAddress.parse(text).value == canonical


@pytest.mark.parametrize(
    "value",
    ["ff:ff:ff:ff:ff:ff", "01:00:5e:00:00:01", "zz:bb:cc:dd:ee:01", "aa:bb"],
)
def test_invalid_mac(value: str) -> None:
    with pytest.raises(InvalidAddressError):
        MacAddress.parse(value)


def test_generated_mac_is_local_unicast() -> None:
    mac = generate_mac(random.Random(42))
    assert mac.value.startswith("02:")
    assert int(mac.value[:2], 16) & 0x01 == 0


def test_subnet_capacity_and_reserved() -> None:
    subnet = Subnet(id=1, network=ipaddress.IPv4Network("10.0.1.0/24"))
    assert subnet.usable_hosts() == 254
    assert subnet.is_reserved(ipaddress.IPv4Address("10.0.1.0"))
    assert subnet.is_reserved(ipaddress.IPv4Address("10.0.1.255"))
    point_to_point = Subnet(id=2, network=ipaddress.IPv4Network("10.0.0.0/31"))
    assert point_to_point.usable_hosts() == 2
    assert not point_to_point.is_reserved(ipaddress.IPv4Address("10.0.0.0"))
    loopback = Subnet(id=3, network=ipaddress.IPv4Network("127.0.0.1/32"))
    assert loopback.usable_hosts() == 1
