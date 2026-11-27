"""Virtualized borderless cursor table."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from netcore.tui.theme import (
    ACCENT_AMBER,
    BG_ROW_FOCUS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

Justify = Literal["default", "left", "center", "right", "full"]


@dataclass(frozen=True, slots=True)
class Column:
    """One table column."""

    name: str
    justify: Justify = "left"
    style: str = TEXT_SECONDARY


def render(
    columns: tuple[Column, ...],
    rows: Sequence[Sequence[object]],
    *,
    selected: int = 0,
    focused: bool = False,
    max_rows: int = 12,
    empty: str = "No data",
    start: int = 0,
) -> RenderableType:
    """Render a flat table with a visible row cursor."""
    if not rows:
        return Group(
            Text(f"  {empty}", style=TEXT_MUTED),
            Text(""),
        )
    visible = list(rows)[start : start + max_rows]
    table = Table(
        box=None,
        expand=True,
        padding=(0, 1),
        show_header=True,
        header_style=TEXT_MUTED,
    )
    table.add_column("", width=2, no_wrap=True)
    for column in columns:
        table.add_column(
            column.name,
            justify=column.justify,
            no_wrap=True,
            overflow="ellipsis",
            style=column.style,
        )
    for index, row in enumerate(visible, start=start):
        is_selected = focused and index == selected
        cursor = Text("▸" if is_selected else " ", style=ACCENT_AMBER)
        cells: list[Text] = [cursor]
        for value in row[: len(columns)]:
            style = f"bold {TEXT_PRIMARY}" if is_selected else TEXT_SECONDARY
            cells.append(Text(str(value), style=style, overflow="ellipsis"))
        table.add_row(*cells, style=f"on {BG_ROW_FOCUS}" if is_selected else None)
    footer = Text(
        f"  showing {start + 1}–{start + len(visible)} of {len(rows)}",
        style=TEXT_MUTED,
    )
    return Group(table, footer if len(rows) > len(visible) else Text(""))
