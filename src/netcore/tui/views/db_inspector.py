"""Real-time SQLite table inspector."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from netcore.application.dto import (
    ColumnStatsDTO,
    DbTableMetaDTO,
    TablePageDTO,
)
from netcore.tui.components import data_table
from netcore.tui.components.data_table import Column
from netcore.tui.state import INSPECTOR_TABLES, Action, AppState
from netcore.tui.theme import ACCENT_AMBER, ACCENT_BLUE, TEXT_MUTED
from netcore.tui.views.base import BaseView, ViewContent

SPARK = "▁▂▃▄▅▆▇█"


def _pulse(values: list[int]) -> str:
    if not values:
        return SPARK[0] * 10
    low, high = min(values), max(values)
    if high == low:
        return SPARK[0] * len(values)
    chars = []
    for value in values[-10:]:
        index = int((value - low) / (high - low) * (len(SPARK) - 1))
        chars.append(SPARK[max(0, min(len(SPARK) - 1, index))])
    return "".join(chars).rjust(10, SPARK[0])


def _numeric_stats(page: TablePageDTO) -> str:
    stats: tuple[ColumnStatsDTO, ...] = page.column_stats
    for stat in stats:
        if stat.mean_val is not None:
            return (
                f"{stat.column} · mean {stat.mean_val:,.2f} · "
                f"p50 {stat.p50_val:,.2f} · p95 {stat.p95_val:,.2f}"
            )
    return "no numeric column in page"


class DbInspectorView(BaseView):
    """The eleventh screen: live SQLite + Pandas + NumPy monitor."""

    id = "db_inspector"
    title = "SQLite Inspector"
    subtitle = "Real-time database tables, Pandas DataFrames & NumPy statistics."

    def actions(self, state: AppState) -> tuple[Action, ...]:
        return (
            Action("pause", "Resume" if state.paused else "Pause"),
            Action("switch_table", "Switch Table"),
            Action("sort_desc", "Sort Desc"),
            Action("col_stats", "Col Stats"),
            Action("export_csv", "Export CSV"),
        )

    def build(self, state: AppState) -> ViewContent:
        snapshot = state.snapshot
        page = snapshot.active_table_page if snapshot else None
        tables: tuple[DbTableMetaDTO, ...] = snapshot.tables if snapshot else ()
        table_meta = next(
            (table for table in tables if table.name == state.inspector_table), None
        )
        rows = page.rows if page else ()
        columns = page.columns if page else ()
        selected = state.cursor("db_rows", len(rows))
        numeric = _numeric_stats(page) if page else "waiting for poll"
        metrics = (
            (
                "Active Table",
                f"{state.inspector_table}  "
                f"({table_meta.row_count if table_meta else 0} rows · "
                f"{len(columns)} cols)",
                f"{len(tables)} tables",
            ),
            (
                "Filter",
                state.search or "none",
                "press / to filter",
            ),
            ("Numeric Col", numeric, f"{page.query_ms if page else 0:.1f} ms poll"),
            (
                "Change Pulse",
                (
                    f"{state.data.get('db_delta', 0):+d} rows · "
                    f"WAL v{snapshot.db_health.data_version}"
                    if snapshot
                    else "—"
                ),
                _pulse(list(state.data.get("db_pulse", []))),
            ),
        )
        strip = Text()
        for table in tables:
            active = table.name == state.inspector_table
            badge = f"{'▶ ' if active else ''}{table.name} {table.row_count}"
            style = (
                f"bold {ACCENT_AMBER} on #1e2330"
                if active
                else (ACCENT_BLUE if table.row_count else TEXT_MUTED)
            )
            strip.append(f" {badge} ", style=style)
            strip.append(" ")
        page_columns: tuple[Column, ...] = tuple(Column(name) for name in columns[:7])
        body = Group(
            Text("  Tables (←/→ or Switch Table)", style=TEXT_MUTED),
            strip,
            Text(""),
            data_table.render(
                page_columns,
                rows,
                selected=selected,
                focused=state.focus.value == "CONTENT",
                max_rows=14,
                empty=f"Table {state.inspector_table} is empty.",
            ),
            Text(
                f"  rows {page.offset + 1 if rows else 0}–"
                f"{page.offset + len(rows) if page else 0} of "
                f"{page.filtered_rows if page else 0} · "
                f"PgUp/PgDn paginate",
                style=TEXT_MUTED,
            )
            if page
            else Text(""),
        )
        return ViewContent(
            metrics=metrics,
            section="SQLite DataFrames",
            body=body,
        )

    def handle_key(self, key, state: AppState) -> bool:  # noqa: ANN001
        snapshot = state.snapshot
        page = snapshot.active_table_page if snapshot else None
        count = len(page.rows) if page else 0
        if key.kind == "UP":
            state.move_cursor("db_rows", -1, count)
            return True
        if key.kind == "DOWN":
            state.move_cursor("db_rows", 1, count)
            return True
        if key.kind in {"LEFT", "RIGHT"}:
            self._cycle_table(state, -1 if key.kind == "LEFT" else 1)
            return True
        if key.kind == "PAGE_UP":
            state.inspector_offset = max(0, state.inspector_offset - 50)
            return True
        if key.kind == "PAGE_DOWN":
            state.inspector_offset += 50
            return True
        return False

    def _cycle_table(self, state: AppState, delta: int) -> None:
        try:
            index = INSPECTOR_TABLES.index(state.inspector_table)
        except ValueError:
            index = 0
        state.inspector_table = INSPECTOR_TABLES[
            (index + delta) % len(INSPECTOR_TABLES)
        ]
        state.inspector_offset = 0
        state.cursors["db_rows"] = 0


__all__ = ["DbInspectorView"]
