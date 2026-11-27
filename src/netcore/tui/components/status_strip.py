"""Live indicator, elapsed timer and cycle metadata."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from netcore.tui.state import AppState
from netcore.tui.theme import ACCENT_AMBER, ACCENT_GREEN, TEXT_MUTED, TEXT_SECONDARY


def render(state: AppState, meta: str = "") -> RenderableType:
    """Left live dot + timer, right metadata."""
    hours, remainder = divmod(state.elapsed_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    table = Table.grid(expand=True)
    table.add_column(ratio=1, no_wrap=True)
    table.add_column(justify="right", no_wrap=True)
    left = Text()
    if state.paused:
        left.append("◐ paused", style=f"bold {ACCENT_AMBER}")
    else:
        left.append("● live", style=f"bold {ACCENT_GREEN}")
    left.append(f" · {hours:02d}:{minutes:02d}:{seconds:02d}", style=TEXT_SECONDARY)
    right = Text(meta, style=TEXT_MUTED)
    table.add_row(left, right)
    return table


__all__ = ["render"]
