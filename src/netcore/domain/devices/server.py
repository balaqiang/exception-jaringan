"""Server end-host model."""

from __future__ import annotations

import ipaddress

from netcore.domain.addressing import MacAddress
from netcore.domain.arp import ArpTable
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.enums import DeviceType
from netcore.domain.interface import NetworkInterface


class Server(NetworkDevice):
    """End host: source and sink, never forwards."""

    device_type = DeviceType.SERVER

    def __init__(
        self,
        hostname: str,
        *,
        device_id: int = 0,
        interface_count: int = 2,
        interfaces: list[NetworkInterface] | None = None,
        default_gateway: ipaddress.IPv4Address | None = None,
        location: str = "",
        description: str = "",
        arp_timeout_s: int = 300,
    ) -> None:
        self.arp_table = ArpTable(arp_timeout_s)
        self.default_gateway = default_gateway
        super().__init__(
            hostname,
            device_id=device_id,
            location=location,
            description=description,
            interfaces=interfaces,
        )
        if interfaces is None:
            for index in range(interface_count):
                self.add_interface(
                    NetworkInterface(
                        name=f"eth{index}",
                        mac=MacAddress(f"02:00:00:01:00:{index + 1:02x}"),
                    )
                )

    def set_default_gateway(self, gateway: ipaddress.IPv4Address | None) -> None:
        """Configure the default gateway."""
        self.default_gateway = gateway

    def receive(self, *args: object, **kwargs: object) -> object:
        """Delegated to the forwarding engine."""
        raise NotImplementedError("Use ForwardingEngine to deliver packets")
