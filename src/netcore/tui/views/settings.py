"""Configuration and lab lifecycle view."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.application.dto import SettingsDTO
from netcore.tui.components import data_table
from netcore.tui.components.data_table import Column
from netcore.tui.state import SETTINGS_FIELDS, Action, AppState
from netcore.tui.theme import TEXT_MUTED
from netcore.tui.views.base import BaseView, ViewContent


class SettingsView(BaseView):
    """Editable settings and sample lab loading."""

    id = "settings"
    title = "Settings"
    subtitle = "Simulation parameters, poll interval and bundled sample labs."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("save_settings", "Save"),
            Action("load_spine", "Load Spine-Leaf"),
            Action("load_two", "Load 2-Router"),
            Action("reset_lab", "Reset Lab", "danger"),
        )

    def build(self, state: AppState) -> ViewContent:
        settings: SettingsDTO | None = state.data.get("settings")
        values: dict[str, str] = state.data.get("settings_values", {}) or {}
        selected = state.cursor("settings", len(SETTINGS_FIELDS))
        metrics = (
            (
                "DB Path",
                settings.db_path if settings else "—",
                "SQLite WAL",
            ),
            (
                "Poll Interval",
                f"{settings.poll_interval_ms} ms" if settings else "—",
                "real-time watcher",
            ),
            (
                "Default TTL",
                str(settings.default_ttl) if settings else "—",
                f"max hops {settings.max_hops}" if settings else "",
            ),
            (
                "Seed",
                str(settings.seed) if settings else "—",
                "deterministic simulation",
            ),
        )
        rows = [(field, values.get(field, "—")) for field in SETTINGS_FIELDS]
        body = Group(
            Text("  Simulation settings (↵ to edit)", style=TEXT_MUTED),
            data_table.render(
                (Column("Key"), Column("Value")),
                rows,
                selected=selected,
                focused=state.focus.value == "CONTENT",
                max_rows=8,
                empty="Settings unavailable.",
            ),
            Text(""),
            Text(
                "  Sample labs replace the current topology; events are kept.",
                style=TEXT_MUTED,
            ),
        )
        return ViewContent(metrics=metrics, section="Configuration", body=body)

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        if key.kind in {"UP", "DOWN"}:
            state.move_cursor(
                "settings", -1 if key.kind == "UP" else 1, len(SETTINGS_FIELDS)
            )
            return True
        return False
