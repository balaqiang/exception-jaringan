"""Analytics read-model, NumPy safety and WAL live updates."""

from __future__ import annotations

import numpy as np
import pytest

from netcore.application.dto import SendPacketRequest
from netcore.application.errors import ApplicationError
from netcore.infrastructure.analytics.metrics_engine import (
    SPARK_CHARS,
    MetricsEngine,
    to_sparkline,
)
from netcore.infrastructure.persistence.connection import open_connection


def test_snapshot_has_all_tables_and_counts(container) -> None:
    snapshot = container.services.analytics.snapshot(active_table="devices")
    assert len(snapshot.tables) == 13
    assert snapshot.device_counts["total"] == 6
    assert snapshot.device_counts["online"] == 6
    assert snapshot.link_counts["total"] == 5
    assert len(snapshot.link_analytics) == 5
    assert snapshot.active_table_page is not None
    assert snapshot.active_table_page.total_rows == 6
    assert snapshot.db_health.journal_mode.lower() == "wal"
    assert snapshot.db_health.total_rows > 0


def test_table_page_filter_sort_and_bounds(container) -> None:
    service = container.services.analytics
    page = service.table_page("devices", limit=2)
    assert len(page.rows) == 2
    assert page.total_rows == 6
    assert len(page.columns) >= 8
    ascending = service.table_page("devices", sort_by="id", descending=False, limit=6)
    assert [int(row[0]) for row in ascending.rows] == [1, 2, 3, 4, 5, 6]
    filtered = service.table_page("devices", search="srv", limit=10)
    assert filtered.filtered_rows == 2
    with pytest.raises(ApplicationError):
        service.table_page("users")


def test_latency_metrics_after_simulation(container) -> None:
    devices = container.services.device.list_devices()
    source = next(item for item in devices if item.hostname == "srv-a")
    result = container.services.simulation.send_packet(
        SendPacketRequest(
            src_device_id=source.device_id,
            dst_ip="10.0.2.10",
            protocol="ICMP",
            ttl=64,
            size_bytes=64,
            payload="analytics",
        )
    )
    assert result.status == "DELIVERED"
    snapshot = container.services.analytics.snapshot()
    assert snapshot.latency is not None
    assert snapshot.latency.sample_count == 1
    assert snapshot.latency.p95_ms >= snapshot.latency.p50_ms
    assert snapshot.latency.max_ms > 0


def test_empty_metrics_and_nan_are_safe() -> None:
    engine = MetricsEngine()
    empty = engine.latency_metrics(np.array([]))
    assert empty.sample_count == 0
    assert empty.mean_ms == 0.0
    assert empty.sparkline == SPARK_CHARS[0] * 10
    dirty = np.array([np.nan, np.inf, -np.inf, 1.0, 2.0])
    metrics = engine.latency_metrics(dirty)
    assert metrics.sample_count == 2
    assert all(
        np.isfinite(value)
        for value in (
            metrics.mean_ms,
            metrics.p50_ms,
            metrics.p95_ms,
            metrics.p99_ms,
            metrics.max_ms,
        )
    )
    spark = to_sparkline(np.array([]), width=7)
    assert len(spark) == 7
    assert set(spark) <= set(SPARK_CHARS)


def test_ema_and_anomaly() -> None:
    engine = MetricsEngine()
    for _ in range(10):
        ema, spark, anomaly = engine.update_link(1, 20.0)
    assert ema == 20.0
    assert len(spark) == 10
    assert not anomaly
    for _ in range(24):
        ema, _spark, anomaly = engine.update_link(2, 95.0)
    assert ema > 90
    assert anomaly


def test_wal_external_write_visible(container) -> None:
    reader = container.reader
    before_version = reader.get_data_version()
    before = container.services.analytics.snapshot()
    before_events = next(
        table.row_count for table in before.tables if table.name == "events"
    )
    writer = open_connection(container.db_path)
    try:
        writer.execute(
            """
            INSERT INTO events(
                timestamp, severity, category, device_id, message, payload_json
            )
            VALUES ('2026-01-01T00:00:00+00:00', 'WARNING', 'SYSTEM', NULL,
                    'external writer', '{}')
            """
        )
        writer.commit()
    finally:
        writer.close()
    after_version = reader.get_data_version()
    assert after_version != before_version
    after = container.services.analytics.snapshot()
    after_events = next(
        table.row_count for table in after.tables if table.name == "events"
    )
    assert after_events == before_events + 1


def test_export_table(container, tmp_path) -> None:
    target = tmp_path / "devices.csv"
    result = container.services.analytics.export_table(
        "devices", str(target), search="srv"
    )
    assert result.rows == 2
    assert target.exists()
    assert "hostname" in target.read_text(encoding="utf-8")
