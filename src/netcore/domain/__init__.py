"""NetCore domain layer: pure standard-library network model."""

from netcore.domain.devices.router import Router
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch
from netcore.domain.topology import NetworkTopology

__all__ = ["NetworkTopology", "Router", "Server", "Switch"]
