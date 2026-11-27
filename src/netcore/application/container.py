"""Service container passed from the composition root to the TUI."""

from __future__ import annotations

from dataclasses import dataclass

from netcore.application.services.analytics_service import AnalyticsService
from netcore.application.services.device_service import DeviceService
from netcore.application.services.event_log_service import EventLogService
from netcore.application.services.ipam_service import IpamService
from netcore.application.services.monitoring_service import MonitoringService
from netcore.application.services.routing_service import RoutingService
from netcore.application.services.settings_service import SettingsService
from netcore.application.services.simulation_service import SimulationService
from netcore.application.services.switch_service import SwitchService
from netcore.application.services.topology_service import TopologyService


@dataclass(frozen=True, slots=True)
class ServiceContainer:
    """All application services handed to the presentation layer."""

    device: DeviceService
    ipam: IpamService
    routing: RoutingService
    switch: SwitchService
    topology: TopologyService
    simulation: SimulationService
    monitoring: MonitoringService
    event_log: EventLogService
    settings: SettingsService
    analytics: AnalyticsService


__all__ = ["ServiceContainer"]
