"""Single composition root (ARCHITECTURE §1.1)."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from netcore.application.container import ServiceContainer
from netcore.application.event_bus import EventBus
from netcore.application.labs import build_two_router_lab
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
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.events import NetworkEvent
from netcore.infrastructure.analytics.db_watcher import RealtimeDbWatcher
from netcore.infrastructure.analytics.metrics_engine import MetricsEngine
from netcore.infrastructure.analytics.sqlite_reader import SqliteSnapshotReader
from netcore.infrastructure.clock import SystemClock
from netcore.infrastructure.persistence.connection import open_connection
from netcore.infrastructure.persistence.migrator import Migrator
from netcore.infrastructure.persistence.unit_of_work import SqliteUnitOfWork

DEFAULT_DB = Path.home() / ".local" / "state" / "netcore" / "netcore.db"


@dataclass(frozen=True, slots=True)
class AppContainer:
    """Runtime dependencies for the Rich app."""

    services: ServiceContainer
    watcher: RealtimeDbWatcher
    reader: SqliteSnapshotReader
    bus: EventBus
    db_path: str


def resolve_db_path(db_path: str | None = None) -> str:
    """CLI flag > NETCORE_DB > default state path."""
    return db_path or os.environ.get("NETCORE_DB") or str(DEFAULT_DB)


def build_container(
    db_path: str | None = None,
    *,
    seed_lab: str | None = "two-router",
) -> AppContainer:
    """Open SQLite, migrate, seed, and wire services."""
    path = resolve_db_path(db_path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = open_connection(path)
    try:
        Migrator(conn).migrate()
    finally:
        conn.close()

    clock = SystemClock()
    bus = EventBus()

    from netcore.application.ports import UnitOfWork

    def factory() -> UnitOfWork:
        return cast(UnitOfWork, SqliteUnitOfWork(path, now=clock.now()))

    if seed_lab and _is_empty(path):
        _seed(path, seed_lab, clock)

    services = ServiceContainer(
        device=DeviceService(factory, clock, bus),
        ipam=IpamService(factory, clock, bus),
        routing=RoutingService(factory, clock, bus),
        switch=SwitchService(factory, clock, bus),
        topology=TopologyService(factory, clock, bus),
        simulation=SimulationService(factory, clock, bus),
        monitoring=MonitoringService(factory, clock, bus),
        event_log=EventLogService(factory, clock, bus),
        settings=SettingsService(factory, clock, bus, db_path=path),
        analytics=AnalyticsService(SqliteSnapshotReader(path, MetricsEngine())),
    )
    reader = SqliteSnapshotReader(path, MetricsEngine())
    watcher = RealtimeDbWatcher(reader, interval_s=0.5)
    bus.subscribe(None, lambda _event: watcher.wake())
    return AppContainer(
        services=services,
        watcher=watcher,
        reader=reader,
        bus=bus,
        db_path=path,
    )


def _is_empty(path: str) -> bool:
    conn: sqlite3.Connection | None = None
    try:
        conn = open_connection(path)
        row = conn.execute("SELECT COUNT(*) FROM devices").fetchone()
        return int(row[0]) == 0
    except sqlite3.Error:
        return True
    finally:
        if conn is not None:
            conn.close()


def _seed(path: str, name: str, clock: SystemClock) -> None:
    from netcore.application.labs import build_spine_leaf_lab

    topology = (
        build_spine_leaf_lab() if name == "spine-leaf" else build_two_router_lab()
    )
    with SqliteUnitOfWork(path, now=clock.now()) as uow:
        uow.topology.save(topology)
        event = NetworkEvent(
            timestamp=clock.now(),
            severity=Severity.INFO,
            category=EventCategory.SYSTEM,
            message=(
                f"Sample lab '{name}' seeded with {len(topology.devices())} devices."
            ),
        )
        uow.events.add(event)
        uow.commit()


__all__ = [
    "AppContainer",
    "ServiceContainer",
    "build_container",
    "resolve_db_path",
]
