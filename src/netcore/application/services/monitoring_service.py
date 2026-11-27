"""Simulated traffic and dashboard use cases."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from netcore.application.dto import (
    DashboardDTO,
    DeviceStatsDTO,
    EventDTO,
    FlowDTO,
    FlowRequest,
    LinkStatsDTO,
)
from netcore.application.errors import ApplicationError
from netcore.application.services.base import (
    ServiceBase,
    make_event,
    maps_errors,
    setting,
)
from netcore.application.services.mappers import link_dto
from netcore.domain.enums import EventCategory, Protocol, Severity
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.traffic import FlowReport, TrafficFlow, TrafficGenerator

SPARK_CHARS = "▁▂▃▄▅▆▇█"
HISTORY = 24


@dataclass(slots=True)
class _ActiveFlow:
    flow_id: int
    report: FlowReport
    src_name: str
    dst_ip: str
    protocol: str
    packet_size: int
    pps: int
    duration_s: int
    started_at: datetime


def sparkline(values: list[float], width: int = 10) -> str:
    """Render a simple Unicode sparkline."""
    if not values:
        return SPARK_CHARS[0] * width
    tail = values[-width:]
    low, high = min(tail), max(tail)
    if high - low < 1e-9:
        return SPARK_CHARS[0] * width
    chars = []
    for value in tail:
        index = int((value - low) / (high - low) * (len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[max(0, min(len(SPARK_CHARS) - 1, index))])
    text = "".join(chars)
    return text.rjust(width, SPARK_CHARS[0])


class MonitoringService(ServiceBase):
    """Active simulated flows and derived counters."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self._flows: dict[int, _ActiveFlow] = {}
        self._next_flow_id = 1
        self._history: dict[int, deque[float]] = {}

    @maps_errors
    def start_flow(self, request: FlowRequest) -> FlowDTO:
        """Start a simulated flow and account its load."""
        if not 1 <= request.packets_per_second <= 100_000:
            raise ApplicationError("APP400", "pps must be 1..100000.")
        if not 1 <= request.duration_s <= 3600:
            raise ApplicationError("APP400", "duration must be 1..3600 seconds.")
        if not 64 <= request.packet_size <= 9000:
            raise ApplicationError("APP400", "packet size must be 64..9000.")
        with self._uow() as uow:
            topology = uow.topology.load()
            settings = self._settings(uow)
            source = topology.get_device(request.src_device_id)
            engine = ForwardingEngine(
                topology,
                now=self._clock.now(),
                seed=setting(settings, "seed", 42),
                max_hops=setting(settings, "max_hops", 64),
            )
            generator = TrafficGenerator()
            report = generator.run(
                TrafficFlow(
                    src_device_id=request.src_device_id,
                    dst_ip=request.dst_ip,
                    protocol=Protocol(request.protocol),
                    packet_size=request.packet_size,
                    packets_per_second=request.packets_per_second,
                    duration_s=request.duration_s,
                    seed=setting(settings, "seed", 42),
                ),
                topology,
                engine,
            )
            if not report.delivered:
                raise ApplicationError(
                    "APP422",
                    f"Flow path failed: "
                    f"{report.drop_reason.value if report.drop_reason else 'NO_ROUTE'}",
                )
            flow_id = self._next_flow_id
            self._next_flow_id += 1
            self._flows[flow_id] = _ActiveFlow(
                flow_id=flow_id,
                report=report,
                src_name=source.hostname,
                dst_ip=request.dst_ip,
                protocol=request.protocol,
                packet_size=request.packet_size,
                pps=request.packets_per_second,
                duration_s=request.duration_s,
                started_at=self._clock.now(),
            )
            self._persist_counters(uow)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.TRAFFIC,
                f"Flow {flow_id} started: {source.hostname} -> {request.dst_ip} "
                f"({report.load_mbps} Mbps sim).",
                payload={"flow_id": flow_id, "load_mbps": report.load_mbps},
            )
            uow.events.add(event)
            self._commit(uow, event)
            return self._flow_dto(self._flows[flow_id])

    @maps_errors
    def stop_flow(self, flow_id: int) -> None:
        """Stop a simulated flow."""
        if flow_id not in self._flows:
            raise ApplicationError("APP404", f"Flow {flow_id} is not active.")
        with self._uow() as uow:
            flow = self._flows.pop(flow_id)
            self._persist_counters(uow)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.TRAFFIC,
                f"Flow {flow_id} stopped ({flow.src_name} -> {flow.dst_ip}).",
                payload={"flow_id": flow_id},
            )
            uow.events.add(event)
            self._commit(uow, event)

    @maps_errors
    def flows(self) -> tuple[FlowDTO, ...]:
        """List active flows with remaining time."""
        return tuple(self._flow_dto(flow) for flow in self._flows.values())

    def _flow_dto(self, flow: _ActiveFlow) -> FlowDTO:
        elapsed = (self._clock.now() - flow.started_at).total_seconds()
        return FlowDTO(
            flow_id=flow.flow_id,
            src_hostname=flow.src_name,
            dst_ip=flow.dst_ip,
            protocol=flow.protocol,
            packet_size=flow.packet_size,
            packets_per_second=flow.pps,
            duration_s=flow.duration_s,
            remaining_s=max(0, int(flow.duration_s - elapsed)),
            load_mbps=flow.report.load_mbps,
            utilization_pct=flow.report.utilization_pct,
            status="ACTIVE" if elapsed < flow.duration_s else "EXPIRED",
        )

    @maps_errors
    def link_stats(self) -> tuple[LinkStatsDTO, ...]:
        """Aggregate active-flow load per link."""
        with self._uow() as uow:
            topology = uow.topology.load()
            result = []
            for link in topology.links():
                reports = [
                    flow.report
                    for flow in self._flows.values()
                    if link.id in flow.report.link_ids
                ]
                load = round(sum(report.load_mbps for report in reports), 2)
                capacity = max(1, link.capacity_mbps)
                utilization = round(min(100.0, load / capacity * 100.0), 1)
                history = self._history.setdefault(link.id, deque(maxlen=HISTORY))
                history.append(utilization)
                dto = link_dto(link, topology)
                packets = sum(report.packets for report in reports)
                dropped = sum(report.dropped_packets for report in reports)
                result.append(
                    LinkStatsDTO(
                        link_id=link.id,
                        label=f"{dto.endpoint_a} <-> {dto.endpoint_b}",
                        capacity_mbps=link.capacity_mbps,
                        load_mbps=load,
                        utilization_pct=utilization,
                        tx_packets=packets,
                        rx_packets=packets,
                        dropped_packets=dropped,
                        sparkline=sparkline(list(history)),
                        admin_up=link.admin_up,
                    )
                )
            return tuple(result)

    @maps_errors
    def device_stats(self) -> tuple[DeviceStatsDTO, ...]:
        """Aggregate active-flow counters per device."""
        with self._uow() as uow:
            topology = uow.topology.load()
            result = []
            for device in topology.devices():
                reports = [
                    flow.report
                    for flow in self._flows.values()
                    if device.id in flow.report.path
                ]
                packets = sum(report.packets for report in reports)
                dropped = sum(report.dropped_packets for report in reports)
                reason = next(
                    (
                        report.drop_reason.value
                        for report in reports
                        if report.drop_reason
                    ),
                    None,
                )
                result.append(
                    DeviceStatsDTO(
                        device_id=device.id,
                        hostname=device.hostname,
                        device_type=device.device_type.value,
                        tx_packets=packets,
                        rx_packets=packets
                        if device.device_type.value == "SERVER"
                        else 0,
                        dropped_packets=dropped,
                        top_drop_reason=reason,
                    )
                )
            return tuple(result)

    @maps_errors
    def reset_counters(self) -> None:
        """Stop every flow and clear counters."""
        self._flows.clear()
        self._history.clear()
        with self._uow() as uow:
            self._persist_counters(uow)
            event = make_event(
                self._clock.now(),
                Severity.INFO,
                EventCategory.TRAFFIC,
                "Traffic counters reset.",
            )
            uow.events.add(event)
            self._commit(uow, event)

    @maps_errors
    def dashboard_summary(self) -> DashboardDTO:
        """Build the dashboard overview."""
        with self._uow() as uow:
            topology = uow.topology.load()
            now = self._clock.now()
            device_counts = {"total": 0, "online": 0, "offline": 0, "maintenance": 0}
            for device in topology.devices():
                device_counts["total"] += 1
                device_counts[device.status.value.lower()] += 1
            link_counts = {"total": len(topology.links()), "up": 0, "down": 0}
            for link in topology.links():
                link_counts["up" if link.admin_up else "down"] += 1
            severity_counts = uow.events.counts_since(now - timedelta(hours=1))
            recent = uow.events.query(limit=10)
            names = {device.id: device.hostname for device in topology.devices()}
            from netcore.application.services.base import event_dto

            links = self.link_stats()
            return DashboardDTO(
                device_counts=device_counts,
                link_counts=link_counts,
                subnet_count=len(topology.subnets()),
                events_1h=sum(severity_counts.values()),
                warnings=severity_counts.get(Severity.WARNING.value, 0),
                errors=severity_counts.get(Severity.ERROR.value, 0),
                top_links=tuple(
                    sorted(links, key=lambda item: item.utilization_pct, reverse=True)[
                        :5
                    ]
                ),
                recent_events=tuple(
                    event_dto(event, names.get(event.device_id or -1))
                    for event in recent
                ),
            )

    def _persist_counters(self, uow) -> None:  # noqa: ANN001
        link_rows: dict[int, list[int]] = {}
        device_rows: dict[int, list[int]] = {}
        for flow in self._flows.values():
            report = flow.report
            for link_id in report.link_ids:
                row = link_rows.setdefault(link_id, [0, 0, 0])
                row[0] += report.packets
                row[1] += report.bytes
                row[2] += report.dropped_packets
            for device_id in report.path:
                row = device_rows.setdefault(device_id, [0, 0, 0])
                row[0] += report.packets
                row[1] += report.bytes
                row[2] += report.dropped_packets
        rows: list[tuple[int | None, int | None, str, int, int, int]] = [
            (None, link_id, "TX", values[0], values[1], values[2])
            for link_id, values in link_rows.items()
        ]
        rows.extend(
            (device_id, None, "TX", values[0], values[1], values[2])
            for device_id, values in device_rows.items()
        )
        uow.simulations.replace_counters(rows)


__all__ = ["EventDTO", "MonitoringService", "sparkline"]
