"""Point-to-point link between two interfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class InterfaceRef:
    """Reference to an interface by owning device id and name."""

    device_id: int
    name: str


@dataclass(slots=True)
class Link:
    """Administrative and simulated properties of a link."""

    id: int
    endpoint_a: InterfaceRef
    endpoint_b: InterfaceRef
    capacity_mbps: int = 1000
    latency_ms: float = 0.1
    admin_up: bool = True

    def peer_of(self, ref: InterfaceRef) -> InterfaceRef:
        """Return the opposite endpoint."""
        return self.endpoint_b if ref == self.endpoint_a else self.endpoint_a

    def connects(self, ref: InterfaceRef) -> bool:
        """Return True when either endpoint matches ``ref``."""
        return ref in (self.endpoint_a, self.endpoint_b)

    @property
    def label(self) -> str:
        """Compact label for tables."""
        return f"{self.endpoint_a.name} <-> {self.endpoint_b.name}"
