"""Live-tailing audit event log."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.application.dto import EventDTO
from netcore.tui.components import data_table
from netcore.tui.components.data_table import Column
from netcore.tui.state import Action, AppState
from netcore.tui.theme import TEXT_MUTED
from netcore.tui.views.base import BaseView, ViewContent


class EventLogsView(BaseView):
    """Filterable event table with export."""

    id = "events"
    title = "Event Logs"
    subtitle = "Live audit trail persisted in SQLite; export via Pandas-ready CSV/JSON."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("tail", "Live Tail"),
            Action("cycle_severity", "Severity"),
            Action("cycle_category", "Category"),
            Action("export_events", "Export"),
        )

    def build(self, state: AppState) -> ViewContent:
        events: tuple[EventDTO, ...] = state.data.get("events", ()) or ()
        selected = state.cursor("events", len(events))
        warnings = sum(1 for event in events if event.severity == "WARNING")
        errors = sum(1 for event in events if event.severity in {"ERROR", "CRITICAL"})
        severity = state.data.get("event_severity") or "ALL"
        category = state.data.get("event_category") or "ALL"
        metrics = (
            ("Total Events", f"{len(events)}", state.data.get("event_total", "")),
            ("Warnings", f"{warnings}", "WARNING"),
            ("Errors", f"{errors}", "ERROR / CRITICAL"),
            ("Filters", f"{severity} · {category}", state.search or "no text filter"),
        )
        rows = [
            (
                event.timestamp[11:19]
                if len(event.timestamp) >= 19
                else event.timestamp,
                event.severity,
                event.category,
                event.device_name or "—",
                event.message[:72],
            )
            for event in events
        ]
        body = Group(
            Text("  Audit stream (newest first)", style=TEXT_MUTED),
            data_table.render(
                (
                    Column("Time UTC"),
                    Column("Sev"),
                    Column("Category"),
                    Column("Device"),
                    Column("Message"),
                ),
                rows,
                selected=selected,
                focused=state.focus.value == "CONTENT",
                max_rows=16,
                empty="No events yet — run a simulation or load a lab.",
            ),
        )
        return ViewContent(metrics=metrics, section="Event Stream", body=body)

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        events = state.data.get("events", ()) or ()
        if key.kind in {"UP", "DOWN"}:
            state.move_cursor("events", -1 if key.kind == "UP" else 1, len(events))
            return True
        return False
