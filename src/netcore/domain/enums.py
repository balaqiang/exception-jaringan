"""Domain enumerations (pure stdlib)."""

from __future__ import annotations

from enum import StrEnum


class DeviceType(StrEnum):
    """Kind of network device."""

    ROUTER = "ROUTER"
    SWITCH = "SWITCH"
    SERVER = "SERVER"


class DeviceStatus(StrEnum):
    """Operational status of a device."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"


class Protocol(StrEnum):
    """L3 protocol carried by a packet."""

    ICMP = "ICMP"
    TCP = "TCP"
    UDP = "UDP"


class RouteType(StrEnum):
    """Origin of a routing entry."""

    CONNECTED = "CONNECTED"
    STATIC = "STATIC"
    DEFAULT = "DEFAULT"


class HopKind(StrEnum):
    """Kind of a simulation hop record."""

    SEND = "SEND"
    ARP = "ARP"
    SWITCH = "SWITCH"
    ROUTE = "ROUTE"
    DELIVER = "DELIVER"
    DROP = "DROP"
    FLOOD = "FLOOD"


class ForwardAction(StrEnum):
    """Decision produced by a device for an incoming frame."""

    FORWARD = "FORWARD"
    DELIVER = "DELIVER"
    DROP = "DROP"
    FLOOD = "FLOOD"


class SimulationStatus(StrEnum):
    """Final status of a simulation run."""

    DELIVERED = "DELIVERED"
    DROPPED = "DROPPED"


class DropReason(StrEnum):
    """Reason a packet was dropped."""

    NO_ROUTE = "NO_ROUTE"
    TTL_EXPIRED = "TTL_EXPIRED"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    LINK_DOWN = "LINK_DOWN"
    INTERFACE_DOWN = "INTERFACE_DOWN"
    PORT_DOWN = "PORT_DOWN"
    ARP_FAILED = "ARP_FAILED"
    NOT_FOR_ME = "NOT_FOR_ME"
    HOP_LIMIT = "HOP_LIMIT"
    NO_INTERFACE = "NO_INTERFACE"
    FILTERED = "FILTERED"
    CONGESTION = "CONGESTION"


class Severity(StrEnum):
    """Event severity."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventCategory(StrEnum):
    """Event category."""

    CONFIG = "CONFIG"
    STATE = "STATE"
    FORWARD = "FORWARD"
    DROP = "DROP"
    DELIVERY = "DELIVERY"
    ARP = "ARP"
    TRAFFIC = "TRAFFIC"
    SYSTEM = "SYSTEM"


class Direction(StrEnum):
    """Traffic counter direction."""

    TX = "TX"
    RX = "RX"


class EntryType(StrEnum):
    """ARP entry kind."""

    DYNAMIC = "DYNAMIC"
    STATIC = "STATIC"
