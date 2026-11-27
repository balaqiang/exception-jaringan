"""Device management view."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.application.dto import DeviceDetailDTO, DeviceDTO
from netcore.tui.components import data_table
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import TEXT_MUTED, status_glyph
from netcore.tui.views.base import BaseView, ViewContent


class DevicesView(BaseView):
    """Device list, CRUD actions and interface inspector."""

    id = "devices"
    title = "Devices"
    subtitle = "Routers, switches and servers — create, edit, cycle status or delete."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("new_device", "New Device"),
            Action("edit_device", "Edit"),
            Action("cycle_status", "Cycle Status"),
            Action("delete_device", "Delete", "danger"),
        )

    def build(self, state: AppState) -> ViewContent:
        devices: tuple[DeviceDTO, ...] = state.data.get("devices", ()) or ()
        selected = state.cursor("devices", len(devices))
        device = devices[selected] if devices else None
        detail: DeviceDetailDTO | None = state.data.get("device_detail")
        metrics = (
            (
                "Selected Hostname",
                device.hostname if device else "—",
                device.device_type if device else "",
            ),
            (
                "Type",
                device.device_type if device else "—",
                f"{device.interface_count} interfaces" if device else "",
            ),
            (
                "Status",
                status_glyph(device.status) if device else "—",
                device.location if device else "",
            ),
            (
                "Gateway / Ports",
                (device.gateway or device.port_count or "—") if device else "—",
                device.description[:26] if device else "",
            ),
        )
        rows = [
            (
                item.hostname,
                item.device_type,
                status_glyph(item.status),
                str(item.interface_count),
                item.location or "—",
                item.description[:32] or "—",
            )
            for item in devices
        ]
        interface_rows = [
            (
                iface.name,
                iface.ip or "—",
                iface.mac,
                "up" if iface.admin_up else "down",
                iface.peer or "—",
            )
            for iface in (detail.interfaces if detail else ())
        ]
        body = Group(
            Text("  Devices", style=TEXT_MUTED),
            data_table.render(
                (
                    Column("Hostname"),
                    Column("Type"),
                    Column("Status"),
                    Column("Ifs", justify="right"),
                    Column("Location"),
                    Column("Description"),
                ),
                rows,
                selected=selected,
                focused=state.focus.value == "CONTENT",
                max_rows=10,
                empty="No devices — press New Device or load a sample lab (0).",
            ),
            Text(""),
            Text(
                f"  Interfaces — {device.hostname if device else 'none selected'}",
                style=TEXT_MUTED,
            ),
            data_table.render(
                (
                    Column("Name"),
                    Column("IP / Prefix"),
                    Column("MAC"),
                    Column("Admin"),
                    Column("Peer"),
                ),
                interface_rows,
                max_rows=6,
                empty="Select an addressed device to inspect interfaces.",
            ),
        )
        return ViewContent(metrics=metrics, section="Device Inventory", body=body)

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        devices = state.data.get("devices", ()) or ()
        if key.kind in {"UP", "DOWN"}:
            state.move_cursor("devices", -1 if key.kind == "UP" else 1, len(devices))
            return True
        return False
