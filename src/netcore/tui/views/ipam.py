"""IPAM subnet and address view."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.application.dto import InterfaceDTO, SubnetDTO
from netcore.tui.components import data_table, sparkline
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import TEXT_MUTED
from netcore.tui.views.base import BaseView, ViewContent


class IpamView(BaseView):
    """Subnet capacity plus assigned addresses."""

    id = "ipam"
    title = "IPAM Subnets"
    subtitle = "CIDR capacity, Pandas-style usage aggregation and address lifecycle."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("new_subnet", "New Subnet"),
            Action("assign_ip", "Assign IP"),
            Action("release_ip", "Release IP"),
            Action("delete_subnet", "Delete", "danger"),
        )

    def build(self, state: AppState) -> ViewContent:
        subnets: tuple[SubnetDTO, ...] = state.data.get("subnets", ()) or ()
        addresses: tuple[InterfaceDTO, ...] = state.data.get("addresses", ()) or ()
        selected = state.cursor("ipam", len(subnets))
        subnet = subnets[selected] if subnets else None
        metrics = (
            (
                "Selected CIDR",
                subnet.cidr if subnet else "—",
                subnet.name if subnet else "",
            ),
            (
                "Gateway",
                subnet.gateway or "—" if subnet else "—",
                f"usable hosts {subnet.total_hosts}" if subnet else "",
            ),
            (
                "Capacity",
                (
                    f"{subnet.used_hosts} used · {subnet.free_hosts} free"
                    if subnet
                    else "—"
                ),
                f"of {subnet.total_hosts}" if subnet else "",
            ),
            (
                "Utilization",
                f"{subnet.utilization_pct:.1f} %" if subnet else "—",
                sparkline.utilization_bar(subnet.utilization_pct, 10) if subnet else "",
            ),
        )
        rows = [
            (
                item.cidr,
                item.name or "—",
                item.gateway or "—",
                str(item.total_hosts),
                str(item.used_hosts),
                str(item.free_hosts),
                f"{item.utilization_pct:4.1f}%",
            )
            for item in subnets
        ]
        address_rows = [
            (
                f"{item.ip}/{item.prefix_len}" if item.ip else "—",
                item.device_name,
                item.name,
                item.mac,
            )
            for item in addresses
        ]
        body = Group(
            Text("  Subnets", style=TEXT_MUTED),
            data_table.render(
                (
                    Column("CIDR"),
                    Column("Name"),
                    Column("Gateway"),
                    Column("Total", justify="right"),
                    Column("Used", justify="right"),
                    Column("Free", justify="right"),
                    Column("Util", justify="right"),
                ),
                rows,
                selected=selected,
                focused=state.focus.value == "CONTENT",
                max_rows=8,
                empty="No subnets — press New Subnet.",
            ),
            Text(""),
            Text(
                f"  Assigned addresses — {subnet.cidr if subnet else 'none'}",
                style=TEXT_MUTED,
            ),
            data_table.render(
                (
                    Column("IP / Prefix"),
                    Column("Device"),
                    Column("Interface"),
                    Column("MAC"),
                ),
                address_rows,
                max_rows=6,
                empty="No addresses assigned in this subnet.",
            ),
        )
        return ViewContent(metrics=metrics, section="Address Plan", body=body)

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        subnets = state.data.get("subnets", ()) or ()
        if key.kind in {"UP", "DOWN"}:
            state.move_cursor("ipam", -1 if key.kind == "UP" else 1, len(subnets))
            return True
        return False
