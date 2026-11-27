"""Device classes."""

from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router, RoutingEntry, RoutingTable
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import MacTable, Switch, SwitchPort

__all__ = [
    "MacTable",
    "NetworkDevice",
    "Router",
    "RoutingEntry",
    "RoutingTable",
    "Server",
    "Switch",
    "SwitchPort",
]
