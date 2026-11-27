"""Simulated ARP table."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta

from netcore.domain.addressing import MacAddress
from netcore.domain.enums import EntryType


@dataclass(frozen=True, slots=True)
class ArpEntry:
    """One IP -> MAC binding."""

    ip: ipaddress.IPv4Address
    mac: MacAddress
    interface: str
    learned_at: datetime
    expires_at: datetime | None
    entry_type: EntryType = EntryType.DYNAMIC


class ArpTable:
    """Per-device ARP cache with simulation-time expiry."""

    def __init__(self, timeout_s: int = 300) -> None:
        self._timeout_s = timeout_s
        self._entries: dict[str, ArpEntry] = {}

    def get(self, ip: ipaddress.IPv4Address, now: datetime) -> MacAddress | None:
        """Return a non-expired binding."""
        entry = self._entries.get(str(ip))
        if entry is None:
            return None
        if entry.expires_at is not None and entry.expires_at <= now:
            del self._entries[str(ip)]
            return None
        return entry.mac

    def learn(
        self,
        ip: ipaddress.IPv4Address,
        mac: MacAddress,
        interface: str,
        now: datetime,
    ) -> None:
        """Learn a dynamic binding."""
        self._entries[str(ip)] = ArpEntry(
            ip=ip,
            mac=mac,
            interface=interface,
            learned_at=now,
            expires_at=now + timedelta(seconds=self._timeout_s),
        )

    def add_static(
        self, ip: ipaddress.IPv4Address, mac: MacAddress, interface: str
    ) -> None:
        """Add a permanent binding."""
        self._entries[str(ip)] = ArpEntry(
            ip=ip,
            mac=mac,
            interface=interface,
            learned_at=datetime.min,
            expires_at=None,
            entry_type=EntryType.STATIC,
        )

    def entries(self, now: datetime) -> tuple[ArpEntry, ...]:
        """Return non-expired entries."""
        return tuple(
            entry
            for entry in self._entries.values()
            if entry.expires_at is None or entry.expires_at > now
        )

    def clear(self) -> None:
        """Drop all entries self."""
        self._entries.clear()
