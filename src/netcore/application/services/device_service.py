"""Device management use cases."""

from __future__ import annotations

import random

from netcore.application.dto import (
    CreateDeviceRequest,
    DeviceDetailDTO,
    DeviceDTO,
    RemovalReportDTO,
    UpdateDeviceRequest,
)
from netcore.application.errors import ApplicationError
from netcore.application.services.base import ServiceBase, make_event, maps_errors
from netcore.application.services.mappers import device_dto, interface_dto
from netcore.domain.addressing import MacAddress
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch
from netcore.domain.enums import DeviceStatus, DeviceType, EventCategory, Severity
from netcore.domain.errors import DuplicateHostnameError, InvalidPortError
from netcore.domain.interface import NetworkInterface
from netcore.domain.topology import NetworkTopology

STATUS_CYCLE = (
    DeviceStatus.ONLINE,
    DeviceStatus.OFFLINE,
    DeviceStatus.MAINTENANCE,
)
TYPE_CODE = {DeviceType.ROUTER: "03", DeviceType.SWITCH: "04", DeviceType.SERVER: "05"}


class DeviceService(ServiceBase):
    """CRUD and status management for network devices."""

    @maps_errors
    def list_devices(
        self,
        search: str = "",
        device_type: str | None = None,
        status: str | None = None,
    ) -> tuple[DeviceDTO, ...]:
        """List devices with optional text/type/status filters."""
        with self._uow() as uow:
            topology = uow.topology.load()
            devices = []
            for device in topology.devices():
                if search and search.lower() not in device.hostname.lower():
                    continue
                if device_type and device.device_type.value != device_type:
                    continue
                if status and device.status.value != status:
                    continue
                devices.append(device_dto(device))
            return tuple(devices)

    @maps_errors
    def detail(self, device_id: int) -> DeviceDetailDTO:
        """Return one device plus its interfaces."""
        with self._uow() as uow:
            topology = uow.topology.load()
            device = topology.get_device(device_id)
            return DeviceDetailDTO(
                device=device_dto(device),
                interfaces=tuple(
                    interface_dto(topology, device, iface)
                    for iface in device.interfaces()
                ),
            )

    @maps_errors
    def create_device(self, request: CreateDeviceRequest) -> DeviceDTO:
        """Create a device with seeded unique MAC addresses."""
        with self._uow() as uow:
            topology = uow.topology.load()
            settings = self._settings(uow)
            seed = int(settings.get("seed", "42"))
            rng = random.Random(seed)
            try:
                device_type = DeviceType(request.device_type)
            except ValueError as exc:
                raise ApplicationError(
                    "APP400", f"Unknown device type {request.device_type}."
                ) from exc
            if topology.find_by_hostname(request.hostname) is not None:
                raise DuplicateHostnameError(
                    f'Hostname "{request.hostname}" already exists.'
                )
            interfaces = self._make_interfaces(
                topology, device_type, request.interface_count, rng
            )
            device = self._make_device(request, device_type, interfaces)
            topology.add_device(device)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Device {device.hostname} ({device.device_type.value}) added.",
                device_id=device.id,
            )
            uow.events.add(event)
            self._commit(uow, event)
            return device_dto(device)

    def _make_device(
        self,
        request: CreateDeviceRequest,
        device_type: DeviceType,
        interfaces: list[NetworkInterface],
    ) -> NetworkDevice:
        if device_type is DeviceType.ROUTER:
            return Router(
                request.hostname,
                location=request.location,
                description=request.description,
                interfaces=interfaces,
            )
        if device_type is DeviceType.SWITCH:
            return Switch(
                request.hostname,
                port_count=len(interfaces),
                location=request.location,
                description=request.description,
                interfaces=interfaces,
            )
        return Server(
            request.hostname,
            location=request.location,
            description=request.description,
            interfaces=interfaces,
        )

    def _make_interfaces(
        self,
        topology: NetworkTopology,
        device_type: DeviceType,
        count: int,
        rng: random.Random,
    ) -> list[NetworkInterface]:
        limits = {
            DeviceType.ROUTER: (1, 16),
            DeviceType.SWITCH: (1, 96),
            DeviceType.SERVER: (1, 8),
        }
        low, high = limits[device_type]
        if not low <= count <= high:
            raise InvalidPortError(
                f"{device_type.value} interface count must be {low}..{high}."
            )
        interfaces: list[NetworkInterface] = []
        prefix = TYPE_CODE[device_type]
        for index in range(1, count + 1):
            name = (
                f"ge0/{index - 1}"
                if device_type is DeviceType.ROUTER
                else f"port{index}"
                if device_type is DeviceType.SWITCH
                else f"eth{index - 1}"
            )
            while True:
                mac = MacAddress(
                    f"02:00:00:{prefix}:{rng.randrange(256):02x}:{rng.randrange(256):02x}"
                )
                if topology.find_interface_by_mac(mac) is None:
                    break
            interfaces.append(
                NetworkInterface(
                    name=name,
                    mac=mac,
                    port_number=index if device_type is DeviceType.SWITCH else None,
                    speed_mbps=1000,
                )
            )
        return interfaces

    @maps_errors
    def update_device(self, request: UpdateDeviceRequest) -> DeviceDTO:
        """Update descriptive fields and hostname."""
        with self._uow() as uow:
            topology = uow.topology.load()
            device = topology.get_device(request.device_id)
            existing = topology.find_by_hostname(request.hostname)
            if existing is not None and existing.id != device.id:
                raise DuplicateHostnameError(
                    f'Hostname "{request.hostname}" already exists.'
                )
            device.hostname = request.hostname
            device.location = request.location
            device.description = request.description
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.CONFIG,
                f"Device {device.hostname} updated.",
                device_id=device.id,
            )
            uow.events.add(event)
            self._commit(uow, event)
            return device_dto(device)

    @maps_errors
    def delete_device(self, device_id: int) -> RemovalReportDTO:
        """Delete a device and its links."""
        with self._uow() as uow:
            topology = uow.topology.load()
            report = topology.remove_device(device_id)
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.WARNING,
                EventCategory.CONFIG,
                f"Device {report.device_name} deleted.",
                payload={"links": len(report.links), "routes": report.routes},
            )
            uow.events.add(event)
            self._commit(uow, event)
            return RemovalReportDTO(
                device_name=report.device_name,
                links=len(report.links),
                routes=report.routes,
                interfaces=report.interfaces,
            )

    @maps_errors
    def set_status(self, device_id: int, status: str) -> DeviceDTO:
        """Set an explicit device status."""
        with self._uow() as uow:
            topology = uow.topology.load()
            device = topology.get_device(device_id)
            device.set_status(DeviceStatus(status))
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.INFO
                if device.status is DeviceStatus.ONLINE
                else Severity.WARNING,
                EventCategory.STATE,
                f"Device {device.hostname} is {device.status.value}.",
                device_id=device.id,
            )
            uow.events.add(event)
            self._commit(uow, event)
            return device_dto(device)

    @maps_errors
    def cycle_status(self, device_id: int) -> DeviceDTO:
        """Cycle ONLINE -> OFFLINE -> MAINTENANCE -> ONLINE."""
        with self._uow() as uow:
            topology = uow.topology.load()
            device = topology.get_device(device_id)
            index = STATUS_CYCLE.index(device.status)
            device.set_status(STATUS_CYCLE[(index + 1) % len(STATUS_CYCLE)])
            uow.topology.save(topology)
            event = make_event(
                self._clock.now(),
                Severity.WARNING
                if device.status is not DeviceStatus.ONLINE
                else Severity.INFO,
                EventCategory.STATE,
                f"Device {device.hostname} is {device.status.value}.",
                device_id=device.id,
            )
            uow.events.add(event)
            self._commit(uow, event)
            return device_dto(device)
