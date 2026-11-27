"""Abstract network device."""

from __future__ import annotations

import ipaddress
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from netcore.domain.enums import DeviceStatus, DeviceType
from netcore.domain.errors import DuplicateInterfaceError, InterfaceNotFoundError
from netcore.domain.interface import NetworkInterface
from netcore.domain.logging_mixin import LoggerMixin

if TYPE_CHECKING:
    pass


class NetworkDevice(LoggerMixin, ABC):
    """Base class for routers, switches and servers (DEC-003)."""

    device_type: DeviceType

    def __init__(
        self,
        hostname: str,
        *,
        device_id: int = 0,
        location: str = "",
        description: str = "",
        interfaces: list[NetworkInterface] | None = None,
    ) -> None:
        super().__init__()
        if not hostname.strip():
            raise ValueError("Hostname must not be empty")
        self._id = device_id
        self._hostname = hostname.strip()
        self._status = DeviceStatus.ONLINE
        self._location = location
        self._description = description
        self._interfaces: dict[str, NetworkInterface] = {}
        for interface in interfaces or []:
            self.add_interface(interface)

    @property
    def id(self) -> int:
        """Surrogate id assigned by the topology."""
        return self._id

    @id.setter
    def id(self, value: int) -> None:
        self._id = value

    @property
    def hostname(self) -> str:
        """Unique lab hostname."""
        return self._hostname

    @hostname.setter
    def hostname(self, value: str) -> None:
        if not value.strip():
            raise ValueError("Hostname must not be empty")
        self._hostname = value.strip()

    @property
    def status(self) -> DeviceStatus:
        """Current operational status."""
        return self._status

    @property
    def location(self) -> str:
        """Free-form location label."""
        return self._location

    @location.setter
    def location(self, value: str) -> None:
        self._location = value

    @property
    def description(self) -> str:
        """Free-form description."""
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = value

    def is_online(self) -> bool:
        """Return True only for ONLINE devices."""
        return self._status is DeviceStatus.ONLINE

    def set_status(self, status: DeviceStatus) -> None:
        """Set the operational status."""
        self._status = status

    def interfaces(self) -> tuple[NetworkInterface, ...]:
        """Return interfaces ordered by name."""
        return tuple(self._interfaces[name] for name in sorted(self._interfaces))

    def get_interface(self, name: str) -> NetworkInterface:
        """Return one interface or raise ``InterfaceNotFoundError``."""
        try:
            return self._interfaces[name]
        except KeyError as exc:
            raise InterfaceNotFoundError(
                f"Interface {name} not found on {self._hostname}."
            ) from exc

    def add_interface(self, interface: NetworkInterface) -> None:
        """Register an interface; names are unique per device."""
        if interface.name in self._interfaces:
            raise DuplicateInterfaceError(
                f"Interface {interface.name} already exists on {self._hostname}."
            )
        self._interfaces[interface.name] = interface

    def replace_interfaces(self, interfaces: list[NetworkInterface]) -> None:
        """Replace all interfaces (used by persistence mappers)."""
        self._interfaces = {interface.name: interface for interface in interfaces}

    def owns_ip(self, ip: ipaddress.IPv4Address) -> bool:
        """Return True when any interface owns ``ip``."""
        return any(iface.ip == ip for iface in self._interfaces.values())

    def addressed_interfaces(self) -> tuple[NetworkInterface, ...]:
        """Return interfaces that have an L3 address."""
        return tuple(iface for iface in self.interfaces() if iface.address is not None)

    def __str__(self) -> str:
        return f"{self.device_type.value} {self._hostname} [{self._status.value}]"

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._hostname} id={self._id}>"

    @abstractmethod
    def receive(self, *args: object, **kwargs: object) -> object:
        """Process an incoming frame (implemented by subclasses)."""
