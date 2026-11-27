"""Immutable L3 packet and L2 frame models."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, replace

from netcore.domain.addressing import MacAddress
from netcore.domain.enums import Protocol


@dataclass(frozen=True, slots=True)
class Packet:
    """An immutable L3 packet."""

    packet_id: int
    src_ip: ipaddress.IPv4Address
    dst_ip: ipaddress.IPv4Address
    protocol: Protocol = Protocol.ICMP
    ttl: int = 64
    size_bytes: int = 64
    payload: str = ""

    def __post_init__(self) -> None:
        if not 1 <= self.ttl <= 255:
            raise ValueError("TTL must be 1..255")
        if not 64 <= self.size_bytes <= 9000:
            raise ValueError("Packet size must be 64..9000 bytes")

    def with_ttl(self, ttl: int) -> Packet:
        """Return a copy with a new TTL."""
        return replace(self, ttl=ttl)

    def __str__(self) -> str:
        return (
            f"{self.src_ip} -> {self.dst_ip} {self.protocol} "
            f"ttl={self.ttl} size={self.size_bytes}"
        )


@dataclass(frozen=True, slots=True)
class ArpMessage:
    """Simulated ARP request/reply payload."""

    target_ip: ipaddress.IPv4Address
    sender_mac: MacAddress
    reply: bool = False


@dataclass(frozen=True, slots=True)
class Frame:
    """An immutable L2 frame."""

    frame_id: int
    src_mac: MacAddress
    dst_mac: MacAddress
    payload: Packet | ArpMessage | None = None

    def is_broadcast(self) -> bool:
        """Return True for the broadcast destination."""
        return self.dst_mac.value == "ff:ff:ff:ff:ff:ff"
