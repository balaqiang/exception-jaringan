"""Analytics orchestration over the read-only query port."""

from __future__ import annotations

from netcore.application.dto import (
    DbHealthDTO,
    DbTableMetaDTO,
    ExportResultDTO,
    RealtimeMonitorSnapshotDTO,
    TablePageDTO,
)
from netcore.application.errors import ApplicationError
from netcore.application.ports import AnalyticsQueryPort


class AnalyticsService:
    """Expose analytics DTOs to the TUI without leaking pandas or sqlite3."""

    def __init__(self, port: AnalyticsQueryPort) -> None:
        self._port = port

    def get_data_version(self) -> int:
        """Return SQLite's data_version counter."""
        return self._port.get_data_version()

    def db_health(self) -> DbHealthDTO:
        """Return database health."""
        return self._port.read_db_health()

    def list_tables(self) -> tuple[DbTableMetaDTO, ...]:
        """Return table metadata."""
        return self._port.list_tables()

    def table_page(
        self,
        table_name: str,
        *,
        search: str = "",
        sort_by: str | None = None,
        descending: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> TablePageDTO:
        """Return one paginated table page."""
        return self._port.query_table_page(
            table_name,
            search=search,
            sort_by=sort_by,
            descending=descending,
            offset=offset,
            limit=limit,
        )

    def snapshot(
        self,
        *,
        active_table: str | None = None,
        table_search: str = "",
        table_sort_by: str | None = None,
        table_descending: bool = True,
        table_offset: int = 0,
        table_limit: int = 50,
    ) -> RealtimeMonitorSnapshotDTO:
        """Return the full real-time monitor snapshot."""
        return self._port.compute_monitor_snapshot(
            active_table=active_table,
            table_search=table_search,
            table_sort_by=table_sort_by,
            table_descending=table_descending,
            table_offset=table_offset,
            table_limit=table_limit,
        )

    def export_table(
        self,
        table_name: str,
        path: str,
        *,
        search: str = "",
        fmt: str = "csv",
    ) -> ExportResultDTO:
        """Export a table using the analytics adapter."""
        exporter = getattr(self._port, "export_table", None)
        if exporter is None:
            raise ApplicationError("APP501", "Analytics export is unavailable.")
        return exporter(table_name, path, search=search, fmt=fmt)
