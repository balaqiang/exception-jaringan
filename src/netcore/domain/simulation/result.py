"""Simulation result value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from netcore.domain.enums import (
    DeviceType,
    DropReason,
    ForwardAction,
    HopKind,
    Protocol,
    SimulationStatus,
)


@dataclass(frozen=True, slots=True)
class HopRecord:
    """One explained decision in a packet trace."""

    index: int
    device_id: int
    device_name: str
    device_type: DeviceType
    kind: HopKind
    ingress: str | None
    egress: str | None
    ttl_in: int | None
    ttl_out: int | None
    matched_route: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Final outcome of a single packet simulation."""

    run_id: int
    status: SimulationStatus
    drop_reason: DropReason | None
    hops: tuple[HopRecord, ...]
    path: tuple[int, ...]
    total_latency_ms: float
    started_at: datetime
    seed: int
    src_device_id: int = 0
    dst_ip: str = ""
    protocol: Protocol = Protocol.ICMP
    ttl: int = 64
    size_bytes: int = 64
    payload: str = ""

    @property
    def delivered(self) -> bool:
        """Return True when the packet was delivered."""
        return self.status is SimulationStatus.DELIVERED


@dataclass(frozen=True, slots=True)
class PacketRequest:
    """Input accepted by the forwarding engine."""

    src_device_id: int
    dst_ip: str
    protocol: Protocol = Protocol.ICMP
    ttl: int = 64
    size_bytes: int = 64
    payload: str = ""


@dataclass(frozen=True, slots=True)
class ForwardDecision:
    """Result of a device processing a frame."""

    action: ForwardAction
    egress: tuple[str, ...] = field(default_factory=tuple)
    frame_id: int | None = None
    drop_reason: DropReason | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class TracerouteHop:
    """One TTL probe result."""

    ttl: int
    router: str | None
    status: str


@dataclass(frozen=True, slots=True)
class TracerouteResult:
    """Full traceroute output."""

    hops: tuple[TracerouteHop, ...]
    delivered: bool
    dst_ip: str
