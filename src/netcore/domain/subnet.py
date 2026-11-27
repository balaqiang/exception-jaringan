"""IPv4 subnet value object."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass


@dataclass(slots=True)
class Subnet:
    """A lab subnet with optional gateway and parent."""

    id: int
    network: ipaddress.IPv4Network
    name: str = ""
    gateway: ipaddress.IPv4Address | None = None
    parent_id: int | None = None

    def contains(self, ip: ipaddress.IPv4Address) -> bool:
        """Return True when ``ip`` belongs to this network."""
        return ip in self.network

    def usable_hosts(self) -> int:
        """Usable host count, honouring /31 and /32 rules."""
        if self.network.prefixlen >= 31:
            return 2 if self.network.prefixlen == 31 else 1
        return max(0, self.network.num_addresses - 2)

    def is_reserved(self, ip: ipaddress.IPv4Address) -> bool:
        """Return True for network/broadcast addresses when applicable."""
        if self.network.prefixlen >= 31:
            return False
        return ip in (self.network.network_address, self.network.broadcast_address)

    @property
    def cidr(self) -> str:
        """Canonical CIDR string."""
        return str(self.network)
