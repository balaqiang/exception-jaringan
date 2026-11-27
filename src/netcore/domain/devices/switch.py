"""Switch, ports and MAC address table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from netcore.domain.addressing import MacAddress
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.enums import DeviceType
from netcore.domain.errors import InvalidPortError
from netcore.domain.interface import NetworkInterface

VALID_SPEEDS = (10, 100, 1000, 10000, 25000, 40000, 100000)


@dataclass(frozen=True, slots=True)
class MacTableEntry:
    """One learned MAC -> port binding."""

    mac: str
    port: int
    learned_at: datetime
    expires_at: datetime


class MacTable:
    """MAC table with simulation-time expiry."""

    def __init__(self, timeout_s: int = 300) -> None:
        self._timeout_s = timeout_s
        self._entries: dict[str, MacTableEntry] = {}

    def learn(self, mac: MacAddress, port: int, now: datetime) -> None:
        """Learn or refresh a binding."""
        self._entries[mac.value] = MacTableEntry(
            mac=mac.value,
            port=port,
            learned_at=now,
            expires_at=now + timedelta(seconds=self._timeout_s),
        )

    def lookup(self, mac: MacAddress, now: datetime) -> int | None:
        """Return the port for a non-expired MAC."""
        entry = self._entries.get(mac.value)
        if entry is None:
            return None
        if entry.expires_at <= now:
            del self._entries[mac.value]
            return None
        return entry.port

    def entries(self, now: datetime) -> tuple[MacTableEntry, ...]:
        """Return non-expired entries."""
        return tuple(
            entry for entry in self._entries.values() if entry.expires_at > now
        )

    def clear(self) -> None:
        """Drop all entries."""
        self._entries.clear()


@dataclass(slots=True)
class SwitchPort:
    """A switch port backed by a NetworkInterface."""

    number: int
    interface: NetworkInterface
    description: str = ""

    @property
    def speed_mbps(self) -> int:
        """Configured port speed."""
        return self.interface.speed_mbps

    @speed_mbps.setter
    def speed_mbps(self, value: int) -> None:
        if value not in VALID_SPEEDS:
            raise InvalidPortError(f"Unsupported port speed {value} Mbps.")
        self.interface.speed_mbps = value

    @property
    def admin_up(self) -> bool:
        """Administrative state."""
        return self.interface.admin_up

    @admin_up.setter
    def admin_up(self, value: bool) -> None:
        self.interface.admin_up = value


class Switch(NetworkDevice):
    """L2 device forwarding only on destination MAC."""

    device_type = DeviceType.SWITCH

    def __init__(
        self,
        hostname: str,
        *,
        device_id: int = 0,
        port_count: int = 24,
        interfaces: list[NetworkInterface] | None = None,
        location: str = "",
        description: str = "",
        mac_timeout_s: int = 300,
    ) -> None:
        if port_count < 1 or port_count > 96:
            raise InvalidPortError("A switch must have 1..96 ports.")
        self.port_count = port_count
        self.mac_table = MacTable(mac_timeout_s)
        self._ports: dict[int, SwitchPort] = {}
        super().__init__(
            hostname,
            device_id=device_id,
            location=location,
            description=description,
            interfaces=interfaces,
        )
        if interfaces is None:
            for number in range(1, port_count + 1):
                interface = NetworkInterface(
                    name=f"port{number}",
                    mac=MacAddress(
                        f"02:00:00:02:{number // 256:02x}:{number % 256:02x}"
                    ),
                    port_number=number,
                    speed_mbps=1000,
                )
                self.add_interface(interface)
                self._ports[number] = SwitchPort(number=number, interface=interface)
        else:
            for interface in interfaces:
                number = interface.port_number or 0
                if number:
                    self._ports[number] = SwitchPort(
                        number=number,
                        interface=interface,
                        description=interface.description,
                    )

    def add_interface(self, interface: NetworkInterface) -> None:
        """Register an interface and expose it as a port when numbered."""
        super().add_interface(interface)
        number = interface.port_number or 0
        if number:
            self._ports[number] = SwitchPort(
                number=number,
                interface=interface,
                description=interface.description,
            )

    def get_port(self, number: int) -> SwitchPort:
        """Return a port or raise ``InvalidPortError``."""
        try:
            return self._ports[number]
        except KeyError as exc:
            raise InvalidPortError(
                f"Port {number} does not exist on {self.hostname} "
                f"(valid: 1-{self.port_count})."
            ) from exc

    def port_interface(self, number: int) -> NetworkInterface:
        """Return the interface backing a port."""
        return self.get_port(number).interface

    def ports(self) -> tuple[SwitchPort, ...]:
        """Return ports ordered by number."""
        return tuple(self._ports[number] for number in sorted(self._ports))

    def set_port_admin(self, number: int, up: bool) -> SwitchPort:
        """Set administrative state of one port."""
        port = self.get_port(number)
        port.admin_up = up
        return port

    def update_port(
        self, number: int, *, speed_mbps: int | None, description: str | None
    ) -> SwitchPort:
        """Update mutable port attributes."""
        port = self.get_port(number)
        if speed_mbps is not None:
            port.speed_mbps = speed_mbps
        if description is not None:
            port.description = description
            port.interface.description = description
        return port

    def receive(self, *args: object, **kwargs: object) -> object:
        """Delegated to the forwarding engine."""
        raise NotImplementedError("Use ForwardingEngine to switch frames")
