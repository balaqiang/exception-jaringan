"""Dashboard overview."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.tui.components import data_table, sparkline
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import TEXT_MUTED
from netcore.tui.views.base import BaseView, ViewContent


def _short(value: str, width: int = 46) -> str:
    return value if len(value) <= width else value[: width - 1] + "…"


class DashboardView(BaseView):
    """Live KPIs, utilization bars and recent events."""

    id = "dashboard"
    title = "Dashboard"
    subtitle = "Real-time data center health, simulated traffic and audit pulse."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("pause", "Resume" if state.paused else "Pause"),
            Action("sample_lab", "Sample Lab"),
            Action("refresh", "Refresh"),
            Action("reset_lab", "Reset", "danger"),
        )

    def build(self, state: AppState) -> ViewContent:
        snapshot = state.snapshot
        if snapshot is None:
            return ViewContent(
                metrics=(
                    ("Devices", "—", ""),
                    ("Links", "—", ""),
                    ("IPAM Used", "—", ""),
                    ("Events (1h)", "—", ""),
                ),
                section="Overview",
                body=Text("  Waiting for the first SQLite snapshot…", style=TEXT_MUTED),
            )
        devices = snapshot.device_counts
        links = snapshot.link_counts
        metrics = (
            (
                "Devices",
                f"{devices.get('total', 0)} total",
                f"● {devices.get('online', 0)} online  "
                f"○ {devices.get('offline', 0)} off  "
                f"◐ {devices.get('maintenance', 0)} maint",
            ),
            (
                "Links (simulated)",
                f"{links.get('up', 0)} up / {links.get('total', 0)} total",
                f"○ {links.get('down', 0)} down",
            ),
            (
                "IPAM Utilization",
                f"{snapshot.subnet_utilization_pct:.1f} %",
                sparkline.utilization_bar(snapshot.subnet_utilization_pct, 10),
            ),
            (
                "Sim Latency",
                (
                    f"mean {snapshot.latency.mean_ms:.2f} ms  "
                    f"p95 {snapshot.latency.p95_ms:.2f} ms"
                    if snapshot.latency
                    else "—"
                ),
                (
                    f"p99 {snapshot.latency.p99_ms:.2f} ms · "
                    f"{snapshot.latency.sample_count} runs"
                    if snapshot.latency
                    else "no runs"
                ),
            ),
        )
        link_rows = [
            (
                "●" if link.admin_up else "○",
                f"#{link.link_id}",
                link.label,
                f"{link.load_mbps:.1f}",
                sparkline.utilization_bar(link.utilization_pct, 10)
                + f" {link.utilization_pct:4.1f}%",
                link.sparkline,
                f"{link.tx_packets:,}",
            )
            for link in snapshot.link_analytics[:8]
        ]
        event_rows = [
            (
                event.timestamp[11:19]
                if len(event.timestamp) >= 19
                else event.timestamp,
                event.severity[0],
                event.category,
                event.device_name or "—",
                _short(event.message),
            )
            for event in snapshot.recent_events[:8]
        ]
        body = Group(
            Text("  Top link utilization (simulated)", style=TEXT_MUTED),
            data_table.render(
                (
                    Column("", style=TEXT_MUTED),
                    Column("#", justify="right"),
                    Column("Link"),
                    Column("Load", justify="right"),
                    Column("Util"),
                    Column("Pulse"),
                    Column("Packets", justify="right"),
                ),
                link_rows,
                max_rows=6,
                empty="No links — load a sample lab with the Sample Lab action.",
            ),
            Text(""),
            Text("  Recent events", style=TEXT_MUTED),
            data_table.render(
                (
                    Column("Time"),
                    Column("S"),
                    Column("Category"),
                    Column("Device"),
                    Column("Message"),
                ),
                event_rows,
                max_rows=5,
                empty="No events yet.",
            ),
        )
        return ViewContent(
            metrics=metrics,
            section="Overview",
            body=body,
        )


__all__ = ["DashboardView"]
