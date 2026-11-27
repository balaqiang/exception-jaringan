"""Application ports implemented by infrastructure."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol, runtime_checkable

from netcore.application.dto import (
    DbHealthDTO,
    DbTableMetaDTO,
    RealtimeMonitorSnapshotDTO,
    TablePageDTO,
)
from netcore.domain.events import NetworkEvent
from netcore.domain.simulation.result import SimulationResult
from netcore.domain.topology import NetworkTopology


class Clock(Protocol):
    """Injectable time source."""

    def now(self) -> datetime: ...


class MonitorPoller(Protocol):
    """Background snapshot poller consumed by the TUI."""

    def start(
        self, on_snapshot: Callable[[RealtimeMonitorSnapshotDTO], None]
    ) -> None: ...

    def stop(self) -> None: ...

    def toggle(self) -> bool: ...

    def set_interval(self, interval_s: float) -> None: ...

    def set_query(
        self,
        table: str | None,
        *,
        search: str = "",
        sort_by: str | None = None,
        descending: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> None: ...

    def refresh_now(self) -> None: ...


class TopologyRepository(Protocol):
    """Whole-aggregate topology persistence."""

    def load(self) -> NetworkTopology: ...

    def save(self, topology: NetworkTopology) -> None: ...


class EventRepository(Protocol):
    """Audit event persistence."""

    def add(self, event: NetworkEvent) -> int: ...

    def query(self, **kwargs: object) -> list[NetworkEvent]: ...

    def counts_since(self, since: datetime) -> dict[str, int]: ...

    def prune(self, keep: int) -> int: ...


class SimulationRepository(Protocol):
    """Simulation run persistence."""

    def save(self, result: SimulationResult) -> int: ...

    def history(self, limit: int = 20) -> list[dict[str, object]]: ...


class SettingsRepository(Protocol):
    """Key/value settings persistence."""

    def get_all(self) -> dict[str, str]: ...

    def update(self, values: dict[str, str]) -> None: ...


class UnitOfWork(Protocol):
    """Transaction-scoped repository bundle."""

    topology: TopologyRepository
    events: EventRepository
    simulations: SimulationRepository
    settings: SettingsRepository

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, *args: object) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


@runtime_checkable
class AnalyticsQueryPort(Protocol):
    """Read-only analytics queries used by the real-time poller."""

    def get_data_version(self) -> int: ...

    def read_db_health(self) -> DbHealthDTO: ...

    def list_tables(self) -> tuple[DbTableMetaDTO, ...]: ...

    def query_table_page(
        self,
        table_name: str,
        *,
        search: str = "",
        sort_by: str | None = None,
        descending: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> TablePageDTO: ...

    def compute_monitor_snapshot(
        self,
        *,
        active_table: str | None = None,
        table_search: str = "",
        table_sort_by: str | None = None,
        table_descending: bool = True,
        table_offset: int = 0,
        table_limit: int = 50,
    ) -> RealtimeMonitorSnapshotDTO: ...
