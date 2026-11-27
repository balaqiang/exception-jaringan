"""Switch port grid and MAC table view."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.application.dto import DeviceDTO, MacEntryDTO, SwitchPortDTO
from netcore.tui.components import data_table
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import (
    ACCENT_AMBER,
    ACCENT_GREEN,
    ACCENT_RED,
    TEXT_MUTED,
    TEXT_ON_AMBER,
)
from netcore.tui.views.base import BaseView, ViewContent


class SwitchPortsView(BaseView):
    """12-per-row port grid with MAC table."""

    id = "switch_ports"
    title = "Switch Ports"
    subtitle = "Administrative port state, speeds and learned MAC addresses."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("switch_device", "Switch Device"),
            Action("toggle_port", "Toggle Port"),
            Action("edit_port", "Edit Port"),
            Action("clear_macs", "Clear MACs", "danger"),
        )

    def build(self, state: AppState) -> ViewContent:
        switches: tuple[DeviceDTO, ...] = state.data.get("switches", ()) or ()
        index = int(state.data.get("switch_index", 0) or 0)
        switch = switches[index % len(switches)] if switches else None
        ports: tuple[SwitchPortDTO, ...] = state.data.get("ports", ()) or ()
        macs: tuple[MacEntryDTO, ...] = state.data.get("macs", ()) or ()
        selected = state.cursor("ports", len(ports))
        up = sum(1 for port in ports if port.admin_up)
        selected_port = ports[selected] if ports else None
        metrics = (
            (
                "Selected Switch",
                switch.hostname if switch else "—",
                f"{len(ports)} ports",
            ),
            ("Ports Up/Down", f"{up} up · {len(ports) - up} down", "admin state"),
            ("MAC Entries", str(len(macs)), "learned dynamically"),
            (
                "Selected Peer",
                selected_port.peer or "—" if selected_port else "—",
                f"port {selected_port.number} · {selected_port.speed_mbps} Mbps"
                if selected_port
                else "",
            ),
        )
        grid = self._grid(ports, selected, state.focus.value == "CONTENT")
        mac_rows = [
            (entry.mac, str(entry.port), f"{entry.age_s:.0f}s") for entry in macs
        ]
        body = Group(
            Text(
                f"  {switch.hostname if switch else 'No switch'} — port grid "
                "(←→ move, Toggle Port)",
                style=TEXT_MUTED,
            ),
            grid,
            Text(""),
            Text("  MAC Address Table", style=TEXT_MUTED),
            data_table.render(
                (
                    Column("MAC"),
                    Column("Port", justify="right"),
                    Column("Age", justify="right"),
                ),
                mac_rows,
                max_rows=6,
                empty="MAC table is empty.",
            ),
        )
        return ViewContent(metrics=metrics, section="Port Administration", body=body)

    def _grid(
        self, ports: tuple[SwitchPortDTO, ...], selected: int, focused: bool
    ) -> Text:
        text = Text()
        for index, port in enumerate(ports):
            marker = "▸" if index == selected and focused else " "
            glyph = "●" if port.admin_up else "○"
            style = ACCENT_GREEN if port.admin_up else ACCENT_RED
            if index == selected and focused:
                text.append(
                    f"[{marker}{port.number:2d}{glyph}] ",
                    style=f"bold {TEXT_ON_AMBER} on {ACCENT_AMBER}",
                )
            else:
                text.append(f"[{marker}{port.number:2d}", style=TEXT_MUTED)
                text.append(glyph, style=style)
                text.append("] ", style=TEXT_MUTED)
            if (index + 1) % 12 == 0:
                text.append("\n")
        if not ports:
            text.append(
                "  No ports — select a switch with Switch Device.", style=TEXT_MUTED
            )
        return text

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        ports = state.data.get("ports", ()) or ()
        if key.kind == "LEFT":
            state.move_cursor("ports", -1, len(ports))
            return True
        if key.kind == "RIGHT":
            state.move_cursor("ports", 1, len(ports))
            return True
        if key.kind == "UP":
            state.move_cursor("ports", -12, len(ports))
            return True
        if key.kind == "DOWN":
            state.move_cursor("ports", 12, len(ports))
            return True
        return False


__all__ = ["SwitchPortsView"]
