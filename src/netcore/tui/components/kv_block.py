"""Borderless label / value / metadata block."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from netcore.tui.theme import TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY


def render(rows: tuple[tuple[str, str, str], ...]) -> RenderableType:
    """Render up to six metric rows with a fixed label column."""
    table = Table(expand=True, box=None, show_header=False, padding=(0, 0))
    table.add_column(width=18, no_wrap=True)
    table.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column(justify="right", no_wrap=True)
    for label, value, meta in rows:
        table.add_row(
            Text(label, style=TEXT_MUTED),
            Text(value, style=TEXT_PRIMARY),
            Text(meta, style=TEXT_SECONDARY),
        )
    return table
