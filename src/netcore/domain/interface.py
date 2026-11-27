"""Network interface model."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field

from netcore.domain.addressing import MacAddress


@dataclass(slots=True)
class NetworkInterface:
    """A device interface with optional L3 address."""

    name: str
    mac: MacAddress
    address: ipaddress.IPv4Interface | None = None
    admin_up: bool = True
    link_id: int | None = None
    port_number: int | None = None
    speed_mbps: int = 1000
    description: str = field(default="")

    @property
    def ip(self) -> ipaddress.IPv4Address | None:
        """Return the bare address, if configured."""
        return self.address.ip if self.address else None

    def assign_address(self, address: ipaddress.IPv4Interface) -> None:
        """Set the interface address."""
        self.address = address

    def clear_address(self) -> None:
        """Remove the interface address."""
        self.address = None

    @property
    def label(self) -> str:
        """Human readable endpoint label."""
        return self.name
