"""IPv4 and MAC value objects with strict validation."""

from __future__ import annotations

import ipaddress
import random
import re
from dataclasses import dataclass

from netcore.domain.errors import InvalidAddressError

_MAC_SEPARATORS = re.compile(r"[-:.]")
_HEX_PAIR = re.compile(r"^[0-9a-f]{2}$")


def parse_ipv4(text: str) -> ipaddress.IPv4Address:
    """Parse a strict dotted-quad IPv4 address."""
    value = _clean(text)
    parts = value.split(".")
    if len(parts) != 4:
        raise InvalidAddressError(f'"{text}" is not a valid IPv4 address.')
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part.startswith("0")):
            raise InvalidAddressError(f'"{text}" is not a valid IPv4 address.')
        if int(part) > 255:
            raise InvalidAddressError(f'"{text}" is not a valid IPv4 address.')
    try:
        return ipaddress.IPv4Address(value)
    except ValueError as exc:
        raise InvalidAddressError(f'"{text}" is not a valid IPv4 address.') from exc


def parse_interface(text: str) -> ipaddress.IPv4Interface:
    """Parse ``addr/prefix`` into an IPv4Interface."""
    value = _clean(text)
    if "/" not in value:
        raise InvalidAddressError(f'"{text}" must include a prefix length.')
    try:
        return ipaddress.IPv4Interface(value)
    except ValueError as exc:
        raise InvalidAddressError(f'"{text}" is not a valid IPv4 interface.') from exc


def parse_network(text: str) -> ipaddress.IPv4Network:
    """Parse a strict IPv4 network (host bits rejected)."""
    value = _clean(text)
    try:
        return ipaddress.IPv4Network(value, strict=True)
    except ValueError as exc:
        raise InvalidAddressError(f'"{text}" is not a valid IPv4 network.') from exc


def _clean(text: str) -> str:
    if not isinstance(text, str):
        raise InvalidAddressError(f'"{text}" is not a valid address.')
    if not text:
        raise InvalidAddressError("Address must not be empty.")
    if text != text.strip() or " " in text:
        raise InvalidAddressError(f'"{text}" is not a valid address.')
    return text


@dataclass(frozen=True, slots=True, order=True)
class MacAddress:
    """Canonical lowercase colon-separated MAC address."""

    value: str

    @classmethod
    def parse(cls, text: str) -> MacAddress:
        """Normalise ``:``/``-``/``.`` separated input."""
        raw = str(text).strip().lower()
        if not raw:
            raise InvalidAddressError("MAC address must not be empty.")
        parts = [part for part in _MAC_SEPARATORS.split(raw) if part]
        if len(parts) == 1 and len(parts[0]) == 12:
            compact = parts[0]
            parts = [compact[i : i + 2] for i in range(0, 12, 2)]
        elif len(parts) == 3 and all(len(part) == 4 for part in parts):
            compact = "".join(parts)
            parts = [compact[i : i + 2] for i in range(0, 12, 2)]
        if len(parts) != 6 or any(not _HEX_PAIR.match(part) for part in parts):
            raise InvalidAddressError(f'"{text}" is not a valid MAC address.')
        value = ":".join(parts)
        first = int(parts[0], 16)
        if value == "ff:ff:ff:ff:ff:ff":
            raise InvalidAddressError("Broadcast MAC cannot be assigned.")
        if first & 0x01:
            raise InvalidAddressError("Multicast MAC cannot be assigned.")
        return cls(value)

    def __str__(self) -> str:
        return self.value


def generate_mac(rng: random.Random, *, index: int = 0) -> MacAddress:
    """Generate a locally administered unicast MAC (``02:`` prefix)."""
    suffix = [rng.randrange(0, 256) for _ in range(5)]
    if index:
        suffix = [(index >> shift) & 0xFF for shift in (32, 24, 16, 8, 0)]
    return MacAddress("02:" + ":".join(f"{octet:02x}" for octet in suffix))
