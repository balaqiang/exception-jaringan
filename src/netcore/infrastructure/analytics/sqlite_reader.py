"""Read-only SQLite + Pandas read-model for the real-time inspector."""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from netcore.application.dto import (
    ColumnStatsDTO,
    DbHealthDTO,
    DbTableMetaDTO,
    EventDTO,
    ExportResultDTO,
    LatencyMetricsDTO,
    LinkAnalyticsDTO,
    RealtimeMonitorSnapshotDTO,
    TablePageDTO,
)
from netcore.application.errors import ApplicationError
from netcore.infrastructure.analytics.metrics_engine import MetricsEngine, to_sparkline
from netcore.infrastructure.persistence.connection import open_read_only

ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "devices",
        "interfaces",
        "links",
        "subnets",
        "routes",
        "arp_entries",
        "mac_entries",
        "events",
        "simulation_runs",
        "hop_records",
        "traffic_counters",
        "settings",
        "schema_migrations",
    }
)


class SqliteSnapshotReader:
    """Implement ``AnalyticsQueryPort`` using a read-only WAL connection."""

    def __init__(
        self,
        db_path: str | Path,
        metrics: MetricsEngine | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._metrics = metrics or MetricsEngine()
        self._local = threading.local()

    # ---------------------------------------------------------------- conn
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = open_read_only(self._db_path)
            self._local.conn = conn
        return conn

    def close(self) -> None:
        """Close the caller thread's connection."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def get_data_version(self) -> int:
        """Return ``PRAGMA data_version`` for change detection."""
        row = self._conn().execute("PRAGMA data_version").fetchone()
        return int(row[0]) if row else 0

    # --------------------------------------------------------------- health
    def read_db_health(self) -> DbHealthDTO:
        """Return file sizes, journal mode and aggregate row counts."""
        start = time.perf_counter()
        conn = self._conn()
        journal = conn.execute("PRAGMA journal_mode").fetchone()
        tables = tuple(sorted(ALLOWED_TABLES))
        total_rows = 0
        for table in tables:
            total_rows += int(
                conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        path = Path(self._db_path)
        wal = Path(f"{self._db_path}-wal")
        data_version = self.get_data_version()
        elapsed = (time.perf_counter() - start) * 1000
        return DbHealthDTO(
            db_path=str(path),
            journal_mode=str(journal[0]) if journal else "unknown",
            file_size_kb=round(path.stat().st_size / 1024, 1) if path.exists() else 0.0,
            wal_size_kb=round(wal.stat().st_size / 1024, 1) if wal.exists() else 0.0,
            data_version=data_version,
            total_tables=len(tables),
            total_rows=total_rows,
            last_poll_ms=round(elapsed, 2),
            polled_at_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        )

    def list_tables(self) -> tuple[DbTableMetaDTO, ...]:
        """Return metadata for the 13 whitelisted tables."""
        conn = self._conn()
        result = []
        for table in sorted(ALLOWED_TABLES):
            count = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            columns = tuple(
                row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')
            )
            last_updated = None
            if table in {"events", "simulation_runs"}:
                row = conn.execute(
                    f'SELECT MAX(timestamp) AS ts FROM "{table}"'
                    if table == "events"
                    else f'SELECT MAX(started_at) AS ts FROM "{table}"'
                ).fetchone()
                last_updated = row["ts"] if row else None
            result.append(
                DbTableMetaDTO(
                    name=table,
                    row_count=count,
                    column_names=columns,
                    last_updated_at=last_updated,
                )
            )
        return tuple(result)

    # ---------------------------------------------------------------- pages
    def query_table_page(
        self,
        table_name: str,
        *,
        search: str = "",
        sort_by: str | None = None,
        descending: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> TablePageDTO:
        """Load a paginated DataFrame slice plus column statistics."""
        if table_name not in ALLOWED_TABLES:
            raise ApplicationError("APP400", f"Table {table_name} is not inspectable.")
        limit = max(1, min(200, limit))
        offset = max(0, offset)
        start = time.perf_counter()
        conn = self._conn()
        columns = [
            row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")')
        ]
        if sort_by is not None and sort_by not in columns:
            raise ApplicationError("APP400", f"Unknown sort column {sort_by}.")
        where = ""
        params: list[object] = []
        if search:
            text_columns = [
                row["name"]
                for row in conn.execute(f'PRAGMA table_info("{table_name}")')
                if str(row["type"]).upper() in {"TEXT", ""}
            ] or columns
            clauses = [f'CAST("{col}" AS TEXT) LIKE ?' for col in text_columns]
            where = "WHERE " + " OR ".join(clauses)
            params.extend([f"%{search}%"] * len(text_columns))
        total = int(conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0])
        filtered = int(
            conn.execute(
                f'SELECT COUNT(*) FROM "{table_name}" {where}',
                tuple(params),
            ).fetchone()[0]
        )
        order = ""
        if sort_by:
            order = f'ORDER BY "{sort_by}" {"DESC" if descending else "ASC"}'
        else:
            order = "ORDER BY rowid DESC"
        sql = f'SELECT * FROM "{table_name}" {where} {order} LIMIT ? OFFSET ?'
        frame = pd.read_sql_query(sql, conn, params=[*params, limit, offset])
        rows = tuple(
            tuple(
                self._display(value, str(frame.columns[index]))
                for index, value in enumerate(row)
            )
            for row in frame.itertuples(index=False, name=None)
        )
        stats = tuple(self._column_stats(frame[column]) for column in frame.columns)
        elapsed = (time.perf_counter() - start) * 1000
        return TablePageDTO(
            table_name=table_name,
            total_rows=total,
            filtered_rows=filtered,
            offset=offset,
            limit=limit,
            columns=tuple(str(column) for column in frame.columns),
            rows=rows,
            column_stats=stats,
            query_ms=round(elapsed, 2),
        )

    _TIME_COLUMNS = frozenset(
        {
            "timestamp",
            "started_at",
            "created_at",
            "updated_at",
            "expires_at",
            "applied_at",
            "polled_at_utc",
        }
    )

    def _display(self, value: object, column: str) -> str:
        if pd.isna(value):
            return ""
        text = str(value)
        if column in self._TIME_COLUMNS and len(text) > 19:
            return text[:19]
        return text

    def _column_stats(self, series: pd.Series) -> ColumnStatsDTO:
        non_null = int(series.notna().sum())
        null = int(series.isna().sum())
        unique = int(series.nunique(dropna=True))
        values = series.dropna()
        min_val = str(values.min()) if not values.empty else None
        max_val = str(values.max()) if not values.empty else None
        mean_val = p50 = p95 = None
        numeric = pd.to_numeric(values, errors="coerce")
        numeric = numeric.dropna()
        if not numeric.empty:
            array = numeric.to_numpy(dtype=np.float64)
            quantiles = self._metrics.column_quantiles(array)
            mean_val = quantiles["mean"]
            p50 = quantiles["p50"]
            p95 = quantiles["p95"]
        return ColumnStatsDTO(
            column=str(series.name),
            dtype=str(series.dtype),
            non_null_count=non_null,
            null_count=null,
            unique_count=unique,
            min_val=min_val,
            max_val=max_val,
            mean_val=mean_val,
            p50_val=p50,
            p95_val=p95,
        )

    # ------------------------------------------------------------- snapshot
    def compute_monitor_snapshot(
        self,
        *,
        active_table: str | None = None,
        table_search: str = "",
        table_sort_by: str | None = None,
        table_descending: bool = True,
        table_offset: int = 0,
        table_limit: int = 50,
    ) -> RealtimeMonitorSnapshotDTO:
        """Build the full real-time dashboard snapshot."""
        conn = self._conn()
        health = self.read_db_health()
        tables = self.list_tables()

        device_counts = {"total": 0, "online": 0, "offline": 0, "maintenance": 0}
        try:
            frame = pd.read_sql_query(
                "SELECT status, COUNT(*) AS total FROM devices GROUP BY status",
                conn,
            )
            for _, row in frame.iterrows():
                device_counts["total"] += int(row["total"])
                device_counts[str(row["status"]).lower()] = int(row["total"])
        except Exception:
            pass
        link_counts = {"total": 0, "up": 0, "down": 0}
        try:
            frame = pd.read_sql_query(
                "SELECT admin_up, COUNT(*) AS total FROM links GROUP BY admin_up",
                conn,
            )
            for _, row in frame.iterrows():
                count = int(row["total"])
                link_counts["total"] += count
                link_counts["up" if int(row["admin_up"]) else "down"] += count
        except Exception:
            pass

        subnet_utilization = self._subnet_utilization(conn)
        latency = self._latency(conn)
        links = self._link_analytics(conn)
        recent = self._recent_events(conn)
        page = None
        if active_table:
            page = self.query_table_page(
                active_table,
                search=table_search,
                sort_by=table_sort_by,
                descending=table_descending,
                offset=table_offset,
                limit=table_limit,
            )
        return RealtimeMonitorSnapshotDTO(
            db_health=health,
            tables=tables,
            device_counts=device_counts,
            link_counts=link_counts,
            subnet_utilization_pct=subnet_utilization,
            latency=latency,
            link_analytics=links,
            recent_events=recent,
            active_table_page=page,
        )

    def _subnet_utilization(self, conn: sqlite3.Connection) -> float:
        try:
            frame = pd.read_sql_query(
                """
                SELECT s.cidr AS cidr, COUNT(i.id) AS used
                FROM subnets s
                LEFT JOIN interfaces i
                    ON i.subnet_id = s.id AND i.ip_address IS NOT NULL
                GROUP BY s.id
                """,
                conn,
            )
        except Exception:
            return 0.0
        if frame.empty:
            return 0.0
        total_usable = 0
        total_used = 0
        for _, row in frame.iterrows():
            try:
                prefix = int(str(row["cidr"]).split("/")[1])
            except (IndexError, ValueError):
                continue
            total_usable += (
                2
                if prefix == 31
                else 1
                if prefix == 32
                else max(0, 2 ** (32 - prefix) - 2)
            )
            total_used += int(row["used"])
        if total_usable == 0:
            return 0.0
        return round(min(100.0, total_used / total_usable * 100.0), 1)

    def _latency(self, conn: sqlite3.Connection) -> LatencyMetricsDTO:
        try:
            frame = pd.read_sql_query(
                "SELECT total_latency_ms FROM simulation_runs "
                "ORDER BY id DESC LIMIT 500",
                conn,
            )
        except Exception:
            return self._metrics.latency_metrics(np.array([]))
        return self._metrics.latency_metrics(frame["total_latency_ms"].to_numpy())

    def _link_analytics(self, conn: sqlite3.Connection) -> tuple[LinkAnalyticsDTO, ...]:
        try:
            frame = pd.read_sql_query(
                """
                SELECT l.id AS link_id, l.capacity_mbps, l.admin_up,
                       da.hostname AS a_host, ia.name AS a_name,
                       db.hostname AS b_host, ib.name AS b_name,
                       COALESCE(SUM(tc.packets), 0) AS packets,
                       COALESCE(SUM(tc.bytes), 0) AS bytes,
                       COALESCE(SUM(tc.dropped), 0) AS dropped
                FROM links l
                JOIN interfaces ia ON ia.id = l.interface_a_id
                JOIN devices da ON da.id = ia.device_id
                JOIN interfaces ib ON ib.id = l.interface_b_id
                JOIN devices db ON db.id = ib.device_id
                LEFT JOIN traffic_counters tc ON tc.link_id = l.id
                GROUP BY l.id
                ORDER BY l.id
                """,
                conn,
            )
        except Exception:
            return ()
        result = []
        for _, row in frame.iterrows():
            capacity = max(1, int(row["capacity_mbps"]))
            load = round(float(row["bytes"]) * 8 / 1_000_000 / 10.0, 3)
            utilization = round(min(100.0, load / capacity * 100.0), 1)
            ema, spark, anomaly = self._metrics.update_link(
                int(row["link_id"]), utilization
            )
            result.append(
                LinkAnalyticsDTO(
                    link_id=int(row["link_id"]),
                    label=(
                        f"{row['a_host']}:{row['a_name']} <-> "
                        f"{row['b_host']}:{row['b_name']}"
                    ),
                    capacity_mbps=capacity,
                    load_mbps=load,
                    utilization_pct=utilization,
                    ema_utilization_pct=ema,
                    tx_packets=int(row["packets"]),
                    rx_packets=int(row["packets"]),
                    dropped_packets=int(row["dropped"]),
                    sparkline=spark,
                    is_anomaly=anomaly,
                    admin_up=bool(row["admin_up"]),
                )
            )
        return tuple(result)

    def _recent_events(self, conn: sqlite3.Connection) -> tuple[EventDTO, ...]:
        try:
            frame = pd.read_sql_query(
                """
                SELECT e.id, e.timestamp, e.severity, e.category, e.device_id,
                       d.hostname AS device_name, e.message, e.payload_json
                FROM events e LEFT JOIN devices d ON d.id = e.device_id
                ORDER BY e.id DESC LIMIT 10
                """,
                conn,
            )
        except Exception:
            return ()
        return tuple(
            EventDTO(
                event_id=int(row["id"]),
                timestamp=str(row["timestamp"]),
                severity=str(row["severity"]),
                category=str(row["category"]),
                device_id=int(row["device_id"]) if pd.notna(row["device_id"]) else None,
                device_name=row["device_name"]
                if pd.notna(row["device_name"])
                else None,
                message=str(row["message"]),
                payload_json=str(row["payload_json"]),
            )
            for _, row in frame.iterrows()
        )

    # --------------------------------------------------------------- export
    def export_table(
        self,
        table_name: str,
        path: str,
        *,
        search: str = "",
        fmt: str = "csv",
    ) -> ExportResultDTO:
        """Export a filtered table to CSV/JSON with pandas."""
        if table_name not in ALLOWED_TABLES:
            raise ApplicationError("APP400", f"Table {table_name} is not inspectable.")
        if fmt not in {"csv", "json"}:
            raise ApplicationError("APP400", "Export format must be csv or json.")
        conn = self._conn()
        columns = [
            row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")')
        ]
        where = ""
        params: list[object] = []
        if search:
            clauses = [f'CAST("{col}" AS TEXT) LIKE ?' for col in columns]
            where = "WHERE " + " OR ".join(clauses)
            params.extend([f"%{search}%"] * len(columns))
        frame = pd.read_sql_query(
            f'SELECT * FROM "{table_name}" {where} LIMIT 5000',
            conn,
            params=params,
        )
        target = Path(path).expanduser()
        if target.suffix.lower() != f".{fmt}":
            target = target.with_suffix(f".{fmt}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "csv":
            frame.to_csv(target, index=False)
        else:
            frame.to_json(target, orient="records", indent=2)
        return ExportResultDTO(path=str(target), fmt=fmt, rows=len(frame))


__all__ = ["ALLOWED_TABLES", "SqliteSnapshotReader", "to_sparkline"]
