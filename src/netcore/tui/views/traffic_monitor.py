"""Live simulated traffic monitor."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.application.dto import FlowDTO
from netcore.tui.components import data_table, sparkline
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import TEXT_MUTED
from netcore.tui.views.base import BaseView, ViewContent


class TrafficMonitorView(BaseView):
    """Link utilization, NumPy percentiles and active flows."""

    id = "traffic"
    title = "Traffic Monitor"
    subtitle = "Real-time simulated flows and vectorized latency percentiles."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("pause", "Resume" if state.paused else "Pause"),
            Action("start_flow", "Start Flow"),
            Action("stop_flow", "Stop Flow"),
            Action("reset_counters", "Reset", "danger"),
        )

    def build(self, state: AppState) -> ViewContent:
        snapshot = state.snapshot
        links = state.data.get("links", ()) or ()
        if snapshot is not None and snapshot.link_analytics and not links:
            links = snapshot.link_analytics
        flows: tuple[FlowDTO, ...] = state.data.get("flows", ()) or ()
        total_load = sum(link.load_mbps for link in links)
        avg_util = (
            sum(link.utilization_pct for link in links) / len(links) if links else 0.0
        )
        drops = sum(link.dropped_packets for link in links)
        latency = snapshot.latency if snapshot else None
        metrics = (
            (
                "Offered Load",
                f"{total_load:.1f} Mbps (sim)",
                f"{len(flows)} active flow{'s' if len(flows) != 1 else ''}",
            ),
            (
                "Avg Utilization",
                f"{avg_util:.1f} %",
                sparkline.utilization_bar(avg_util, 10),
            ),
            (
                "Packet Drops",
                f"{drops:,} pkts (sim)",
                "CONGESTION" if drops else "none",
            ),
            (
                "Sim Latency",
                (
                    f"mean {latency.mean_ms:.2f} ms · p50 {latency.p50_ms:.2f} ms"
                    if latency
                    else "mean — · p50 —"
                ),
                (
                    f"p95 {latency.p95_ms:.2f} · p99 {latency.p99_ms:.2f}"
                    if latency
                    else "no samples"
                ),
            ),
        )
        link_rows = [
            (
                "●" if link.admin_up else "○",
                link.label,
                f"{link.capacity_mbps}",
                sparkline.utilization_bar(link.utilization_pct, 10)
                + f" {link.utilization_pct:4.1f}%",
                link.sparkline,
                f"{link.tx_packets:,}",
                f"{link.dropped_packets:,}",
            )
            for link in links
        ]
        flow_rows = [
            (
                f"#{flow.flow_id}",
                flow.src_hostname,
                flow.dst_ip,
                flow.protocol,
                f"{flow.packets_per_second} pps",
                f"{flow.load_mbps:.1f}",
                f"{flow.remaining_s}s",
                flow.status,
            )
            for flow in flows
        ]
        body = Group(
            Text(
                "  Active Links (simulated values, not measurements)", style=TEXT_MUTED
            ),
            data_table.render(
                (
                    Column("", style=TEXT_MUTED),
                    Column("Link"),
                    Column("Mbps", justify="right"),
                    Column("Util"),
                    Column("Pulse"),
                    Column("Packets", justify="right"),
                    Column("Drop", justify="right"),
                ),
                link_rows,
                selected=state.cursor("traffic_links", len(link_rows)),
                focused=state.focus.value == "CONTENT",
                max_rows=8,
                empty="No links — load a sample lab in Settings (0).",
            ),
            Text(""),
            Text("  Active Flows", style=TEXT_MUTED),
            data_table.render(
                (
                    Column("Flow"),
                    Column("Source"),
                    Column("Destination"),
                    Column("Proto"),
                    Column("Rate"),
                    Column("Mbps", justify="right"),
                    Column("Left", justify="right"),
                    Column("State"),
                ),
                flow_rows,
                selected=state.cursor("traffic_flows", len(flow_rows)),
                focused=state.focus.value == "CONTENT",
                max_rows=4,
                empty="No active flows — press Start Flow.",
            ),
        )
        return ViewContent(metrics=metrics, section="Traffic & Telemetry", body=body)

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        if key.kind in {"UP", "DOWN"}:
            state.move_cursor(
                "traffic_flows",
                -1 if key.kind == "UP" else 1,
                len(state.data.get("flows", ()) or ()),
            )
            return True
        return False


__all__ = ["TrafficMonitorView"]
