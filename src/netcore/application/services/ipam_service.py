"""IP address management use cases."""

from __future__ import annotations

from itertools import islice

from netcore.application.dto import (
    AssignAddressRequest,
    InterfaceDTO,
    SubnetDTO,
    SubnetRequest,
)
from netcore.application.errors import ApplicationError
from netcore.application.services.base import ServiceBase, make_event, maps_errors
from netcore.application.services.mappers import interface_dto, subnet_dto
from netcore.domain.addressing import parse_ipv4, parse_network
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.errors import AddressNotInSubnetError
from netcore.domain.subnet import Subnet


class IpamService(ServiceBase):
    """Subnet and address lifecycle."""

    @maps_errors
    def list_subnets(self) -> tuple[SubnetDTO, ...]:
        """List subnets with used/free counts."""
        with self._uow() as uow:
            topology = uow.topology.load()
            result = []
            for subnet in topology.subnets():
                used = sum(
                    1
                    for _, interface in topology.addressed_interfaces()
                    if interface.ip is not None and interface.ip in subnet.network
                )
                result.append(subnet_dto(subnet, used))
            return tuple(result)

    @maps_errors
    def create_subnet(self, request: SubnetRequest) -> SubnetDTO:
        """Create a strict, non-overlapping subnet."""
        with self._uow() as uow:
            topology = uow.topology.load()
            network = parse_network(request.cidr)
            gateway = None
            if request.gateway.strip():
                gateway = parse_ipv4(request.gateway)
                if gateway not in network or gateway in (
                    network.network_address,
                    network.broadcast_address,
                ):
                    raise AddressNotInSubnetError(
                        f"{gateway} is not a usable address of {network}."
                    )
            subnet = Subnet(id=0, network=network, name=request.name, gateway=gateway)
            topology.add_subnet(subnet)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Subnet {subnet.network} added.",
            )
            uow.events.add(event)
            self._commit(uow, event)
            return subnet_dto(subnet, 0)

    @maps_errors
    def assign_address(self, request: AssignAddressRequest) -> InterfaceDTO:
        """Assign a validated address to an interface."""
        with self._uow() as uow:
            topology = uow.topology.load()
            interface = topology.assign_address(
                request.device_id, request.interface_name, request.address
            )
            device = topology.get_device(request.device_id)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Address {interface.address} assigned to "
                f"{device.hostname} {interface.name}.",
                device_id=device.id,
            )
            uow.events.add(event)
            self._commit(uow, event)
            return interface_dto(topology, device, interface)

    @maps_errors
    def release_address(self, device_id: int, interface_name: str) -> None:
        """Release an interface address."""
        with self._uow() as uow:
            topology = uow.topology.load()
            device = topology.get_device(device_id)
            topology.release_address(device_id, interface_name)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Address released from {device.hostname} {interface_name}.",
                device_id=device.id,
            )
            uow.events.add(event)
            self._commit(uow, event)

    @maps_errors
    def list_addresses(self, subnet_id: int) -> tuple[InterfaceDTO, ...]:
        """List interfaces addressed inside a subnet."""
        with self._uow() as uow:
            topology = uow.topology.load()
            subnet = topology.get_subnet(subnet_id)
            result = []
            for device, interface in topology.addressed_interfaces():
                if interface.ip is not None and interface.ip in subnet.network:
                    result.append(interface_dto(topology, device, interface))
            return tuple(result)

    @maps_errors
    def next_free_address(self, subnet_id: int) -> str | None:
        """Return the first free usable address in a subnet."""
        with self._uow() as uow:
            topology = uow.topology.load()
            subnet = topology.get_subnet(subnet_id)
            used = {
                interface.ip
                for _, interface in topology.addressed_interfaces()
                if interface.ip is not None
            }
            for host in islice(subnet.network.hosts(), 65_536):
                if host in used or host == subnet.gateway:
                    continue
                return f"{host}/{subnet.network.prefixlen}"
            return None

    @maps_errors
    def delete_subnet(self, subnet_id: int) -> None:
        """Delete a subnet only when no interface uses it."""
        with self._uow() as uow:
            topology = uow.topology.load()
            subnet = topology.get_subnet(subnet_id)
            for _, interface in topology.addressed_interfaces():
                if interface.ip is not None and interface.ip in subnet.network:
                    raise ApplicationError(
                        "APP409",
                        f"Subnet {subnet.network} is still in use by "
                        f"{interface.ip}; release addresses first.",
                    )
            topology._subnets.pop(subnet_id, None)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.WARNING,
                EventCategory.CONFIG,
                f"Subnet {subnet.network} deleted.",
            )
            uow.events.add(event)
            self._commit(uow, event)


__all__ = ["IpamService"]
