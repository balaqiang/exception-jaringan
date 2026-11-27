"""Routing table view with interactive LPM lookup."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.application.dto import DeviceDTO, RouteDTO, RouteLookupDTO
from netcore.tui.components import data_table
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import ACCENT_BLUE, TEXT_MUTED
from netcore.tui.views.base import BaseView, ViewContent


class RoutingView(BaseView):
    """Router selector, route table and longest-prefix tester."""

    id = "routing"
    title = "Routing Table"
    subtitle = "Connected, static and default routes with integer longest-prefix match."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("switch_router", "Switch Router"),
            Action("add_route", "Add Route"),
            Action("lpm_lookup", "LPM Lookup"),
            Action("delete_route", "Delete", "danger"),
        )

    def build(self, state: AppState) -> ViewContent:
        routers: tuple[DeviceDTO, ...] = state.data.get("routers", ()) or ()
        index = int(state.data.get("router_index", 0) or 0)
        router = routers[index % len(routers)] if routers else None
        routes: tuple[RouteDTO, ...] = state.data.get("routes", ()) or ()
        lookup: RouteLookupDTO | None = state.data.get("lookup")
        selected = state.cursor("routing", len(routes))
        connected = sum(1 for route in routes if route.route_type == "CONNECTED")
        static = sum(1 for route in routes if route.route_type == "STATIC")
        default = sum(1 for route in routes if route.route_type == "DEFAULT")
        metrics = (
            (
                "Selected Router",
                router.hostname if router else "—",
                f"{len(routes)} routes",
            ),
            (
                "Route Mix",
                f"{connected} C · {static} S · {default} D",
                "connected / static / default",
            ),
            (
                "Last LPM Match",
                lookup.message if lookup else "press LPM Lookup",
                "longest prefix wins",
            ),
            (
                "Tie Break",
                "AD → metric → insertion",
                "NETWORK_SPEC §6.2",
            ),
        )
        rows = [
            (
                route.route_type[0],
                route.destination,
                route.next_hop or "connected",
                route.interface,
                str(route.admin_distance),
                str(route.metric),
            )
            for route in routes
        ]
        body = Group(
            Text(
                f"  {router.hostname if router else 'No router'} — routing table",
                style=TEXT_MUTED,
            ),
            data_table.render(
                (
                    Column("T"),
                    Column("Destination"),
                    Column("Next Hop"),
                    Column("Interface"),
                    Column("AD", justify="right"),
                    Column("Metric", justify="right"),
                ),
                rows,
                selected=selected,
                focused=state.focus.value == "CONTENT",
                max_rows=14,
                empty="No routes — assign an address or add a static route.",
            ),
            Text(
                (
                    f"  {lookup.message}"
                    if lookup
                    else (
                        "  Press LPM Lookup, enter a destination IP, "
                        "and the match is shown here."
                    )
                ),
                style=ACCENT_BLUE if lookup and lookup.found else TEXT_MUTED,
            ),
        )
        return ViewContent(metrics=metrics, section="Forwarding Table", body=body)

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        routes = state.data.get("routes", ()) or ()
        if key.kind in {"UP", "DOWN"}:
            state.move_cursor("routing", -1 if key.kind == "UP" else 1, len(routes))
            return True
        return False
