"""Layered topology canvas and link list."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text

from netcore.application.dto import LinkDTO, TopologyDTO, TopologyNodeDTO
from netcore.tui.components import data_table
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import (
    ACCENT_GREEN,
    ACCENT_PURPLE,
    ACCENT_RED,
    TEXT_MUTED,
    TEXT_SECONDARY,
    status_glyph,
)
from netcore.tui.views.base import BaseView, ViewContent


class TopologyView(BaseView):
    """ASCII/Unicode layered topology plus link administration."""

    id = "topology"
    title = "Topology"
    subtitle = (
        "Routers, switches and servers; toggle links and highlight the last path."
    )

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("add_link", "Add Link"),
            Action("toggle_link", "Toggle Link"),
            Action("highlight_path", "Highlight Path"),
            Action("list_mode", "List View" if not state.list_mode else "Canvas View"),
        )

    def build(self, state: AppState) -> ViewContent:
        topology: TopologyDTO | None = state.data.get("topology")
        links: tuple[LinkDTO, ...] = state.data.get("links", ()) or ()
        selected = state.cursor("topology", len(links))
        nodes = topology.nodes if topology else ()
        down = sum(1 for link in links if not link.admin_up)
        metrics = (
            ("Nodes", str(len(nodes)), f"{len(links)} links"),
            (
                "Types",
                (
                    f"{sum(1 for n in nodes if n.device_type == 'ROUTER')} R · "
                    f"{sum(1 for n in nodes if n.device_type == 'SWITCH')} S · "
                    f"{sum(1 for n in nodes if n.device_type == 'SERVER')} H"
                ),
                "router / switch / host",
            ),
            ("Down Links", str(down), "shown dashed in red"),
            (
                "Highlighted Path",
                f"{len(state.last_path)} hops" if state.last_path else "none",
                "last simulation",
            ),
        )
        body: list[RenderableType] = []
        if state.list_mode:
            body.append(Text("  Adjacency list", style=TEXT_MUTED))
            body.append(
                data_table.render(
                    (
                        Column("Device"),
                        Column("Type"),
                        Column("Status"),
                        Column("Ifs", justify="right"),
                    ),
                    [
                        (
                            node.hostname,
                            node.device_type,
                            status_glyph(node.status),
                            str(node.interface_count),
                        )
                        for node in nodes
                    ],
                    selected=0,
                    max_rows=16,
                    empty="No devices.",
                )
            )
        else:
            body.append(Text("  Layered canvas", style=TEXT_MUTED))
            body.append(self._canvas(nodes, state.last_path))
            body.append(Text(""))
            body.append(Text("  Links", style=TEXT_MUTED))
            body.append(
                data_table.render(
                    (
                        Column("", style=TEXT_MUTED),
                        Column("Endpoint A"),
                        Column("Endpoint B"),
                        Column("Mbps", justify="right"),
                        Column("Latency", justify="right"),
                    ),
                    [
                        (
                            "●" if link.admin_up else "○",
                            link.endpoint_a,
                            link.endpoint_b,
                            str(link.capacity_mbps),
                            f"{link.latency_ms:.2f} ms",
                        )
                        for link in links
                    ],
                    selected=selected,
                    focused=state.focus.value == "CONTENT",
                    max_rows=6,
                    empty="No links — press Add Link.",
                )
            )
        return ViewContent(
            metrics=metrics,
            section="Topology Map",
            body=Group(*body),
        )

    def _canvas(
        self, nodes: tuple[TopologyNodeDTO, ...], path: tuple[int, ...]
    ) -> Text:
        levels = (
            ("ROUTER", "routers"),
            ("SWITCH", "switches"),
            ("SERVER", "servers"),
        )
        text = Text()
        for device_type, label in levels:
            group = [node for node in nodes if node.device_type == device_type]
            text.append(f"  {label:<9}", style=TEXT_MUTED)
            if not group:
                text.append("—\n", style=TEXT_MUTED)
                continue
            for node in group:
                highlighted = node.device_id in path
                glyph = "●" if node.status == "ONLINE" else "○"
                style = (
                    f"bold {ACCENT_PURPLE}"
                    if highlighted
                    else ACCENT_GREEN
                    if node.status == "ONLINE"
                    else ACCENT_RED
                )
                text.append(f"{glyph} ", style=style)
                text.append(
                    node.hostname,
                    style=f"bold {ACCENT_PURPLE}" if highlighted else TEXT_SECONDARY,
                )
                text.append("   ", style=TEXT_MUTED)
            text.append("\n")
        return text

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        links = state.data.get("links", ()) or ()
        if key.kind in {"UP", "DOWN"}:
            state.move_cursor("topology", -1 if key.kind == "UP" else 1, len(links))
            return True
        return False
