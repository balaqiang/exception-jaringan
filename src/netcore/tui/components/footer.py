"""Context-aware bottom keybinding hints."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from netcore.tui.state import AppState, FocusZone
from netcore.tui.theme import BG_HEADER, TEXT_MUTED, TEXT_PRIMARY

BASE_HINTS = (
    ("↑↓", "navigate"),
    ("←→", "action"),
    ("↵", "run"),
    ("tab", "focus"),
    ("/", "filter"),
    ("space", "pause"),
    ("r", "refresh"),
    ("esc", "back"),
    ("q", "quit"),
)


def render(state: AppState) -> RenderableType:
    """One muted line of shortcuts."""
    hints = list(BASE_HINTS)
    if state.filter_active:
        hints.insert(0, ("typing", "filter · ↵ apply"))
    if state.modal is not None:
        hints = [
            ("↑↓", "field"),
            ("↵", "submit"),
            ("esc", "cancel"),
        ]
    table = Table(
        expand=True,
        box=None,
        show_header=False,
        padding=(0, 1),
        style=f"on {BG_HEADER}",
    )
    table.add_column(ratio=1, no_wrap=True)
    table.add_column(justify="right", no_wrap=True)
    line = Text(" ")
    for index, (key, label) in enumerate(hints):
        line.append(key, style=f"bold {TEXT_PRIMARY}")
        line.append(f" {label}", style=TEXT_MUTED)
        if index < len(hints) - 1:
            line.append("   ", style=TEXT_MUTED)
    focus = Text("focus:", style=TEXT_MUTED)
    focus.append(state.focus.value, style=f"bold {TEXT_PRIMARY}")
    if state.focus is FocusZone.MODAL:
        focus = Text("modal", style=TEXT_MUTED)
    table.add_row(line, focus)
    return table
