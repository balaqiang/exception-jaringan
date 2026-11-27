"""Packet simulation lab and traceroute view."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text

from netcore.application.dto import (
    SimulationResultDTO,
    SimulationSummaryDTO,
    TracerouteDTO,
)
from netcore.tui.components import data_table
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import ACCENT_GREEN, ACCENT_RED, TEXT_MUTED
from netcore.tui.views.base import BaseView, ViewContent


class PacketLabView(BaseView):
    """Send a packet or run traceroute with an explained hop trace."""

    id = "packet_lab"
    title = "Packet Lab"
    subtitle = "Deterministic packet delivery, ARP, TTL and drop-reason trace."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("send_packet", "Send Packet"),
            Action("traceroute", "Traceroute"),
            Action("history", "History"),
            Action("clear_result", "Clear", "danger"),
        )

    def build(self, state: AppState) -> ViewContent:
        result: SimulationResultDTO | None = state.data.get("sim_result")
        trace: TracerouteDTO | None = state.data.get("traceroute")
        history: tuple[SimulationSummaryDTO, ...] = state.data.get("history", ()) or ()
        mode = state.data.get("packet_mode", "trace")
        metrics = (
            (
                "Last Status",
                f"✔ {result.status}"
                if result and result.status == "DELIVERED"
                else (f"✖ {result.status}" if result else "—"),
                result.drop_reason or "" if result else "",
            ),
            (
                "Hops",
                str(len(result.hops)) if result else "—",
                f"path {len(result.path_names)} devices" if result else "",
            ),
            (
                "TTL Delta",
                f"{result.ttl_in} → {result.ttl_out}" if result else "—",
                "routers only",
            ),
            (
                "Sim Latency",
                f"{result.total_latency_ms:.3f} ms" if result else "—",
                "simulated, not measured",
            ),
        )
        body: list[RenderableType] = []
        if result:
            body.append(
                Text(
                    "  Path: " + " → ".join(result.path_names),
                    style=ACCENT_GREEN if result.status == "DELIVERED" else ACCENT_RED,
                )
            )
        if mode == "traceroute" and trace:
            body.append(Text("  Traceroute probes", style=TEXT_MUTED))
            body.append(
                data_table.render(
                    (
                        Column("TTL", justify="right"),
                        Column("Router"),
                        Column("Status"),
                    ),
                    [
                        (str(hop.ttl), hop.router or "*", hop.status)
                        for hop in trace.hops
                    ],
                    max_rows=14,
                    empty="No probes.",
                )
            )
        elif mode == "history":
            body.append(Text("  Recent runs", style=TEXT_MUTED))
            body.append(
                data_table.render(
                    (
                        Column("Run", justify="right"),
                        Column("Source"),
                        Column("Destination"),
                        Column("Status"),
                        Column("Latency", justify="right"),
                    ),
                    [
                        (
                            f"#{run.run_id}",
                            run.src_name,
                            run.dst_ip,
                            run.status,
                            f"{run.total_latency_ms:.2f} ms",
                        )
                        for run in history
                    ],
                    max_rows=14,
                    empty="No simulation history yet.",
                )
            )
        else:
            hops = result.hops if result else ()
            selected = state.cursor("hops", len(hops))
            body.append(Text("  Hop trace", style=TEXT_MUTED))
            body.append(
                data_table.render(
                    (
                        Column("#", justify="right"),
                        Column("Kind"),
                        Column("Device"),
                        Column("In → Out"),
                        Column("TTL"),
                        Column("Decision"),
                    ),
                    [
                        (
                            str(hop.index),
                            hop.kind,
                            hop.device_name,
                            f"{hop.ingress or '—'} → {hop.egress or '—'}",
                            (
                                f"{hop.ttl_in}→{hop.ttl_out}"
                                if hop.ttl_in is not None
                                else "—"
                            ),
                            (hop.matched_route or hop.reason)[:44],
                        )
                        for hop in hops
                    ],
                    selected=selected,
                    focused=state.focus.value == "CONTENT",
                    max_rows=14,
                    empty="No trace yet — press Send Packet.",
                )
            )
            if hops and selected < len(hops):
                body.append(Text(f"  {hops[selected].reason}", style=TEXT_MUTED))
        return ViewContent(
            metrics=metrics,
            section="Simulation Trace",
            body=Group(*body),
        )

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        result: SimulationResultDTO | None = state.data.get("sim_result")
        hops = result.hops if result else ()
        if key.kind in {"UP", "DOWN"}:
            state.data["packet_mode"] = "trace"
            state.move_cursor("hops", -1 if key.kind == "UP" else 1, len(hops))
            return True
        return False
