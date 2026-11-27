"""Left-accented floating notification card."""

from __future__ import annotations

import time

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from netcore.tui.state import AppState
from netcore.tui.theme import (
    ACCENT_AMBER,
    ACCENT_GREEN,
    ACCENT_RED,
    BG_TOAST,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def render(state: AppState, width: int = 34) -> RenderableType:
    """Render the active toast, or a blank surface."""
    toast = state.toast
    if toast is None or time.monotonic() >= toast.expires_at:
        return Text("")
    accent = {
        "info": ACCENT_GREEN,
        "success": ACCENT_GREEN,
        "warning": ACCENT_AMBER,
        "error": ACCENT_RED,
    }.get(toast.severity, ACCENT_GREEN)
    table = Table.grid(expand=True)
    table.add_column(width=1, no_wrap=True)
    table.add_column(ratio=1)
    body = Text(style=f"on {BG_TOAST}")
    body.append(f" {toast.message[: width - 3]}", style=f"bold {TEXT_PRIMARY}")
    if toast.subtitle:
        body.append(f"\n {toast.subtitle[: width - 3]}", style=TEXT_MUTED)
    table.add_row(Text("█", style=accent), body)
    return table
