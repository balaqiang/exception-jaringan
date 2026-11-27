"""Flat modal overlay card."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from netcore.tui.state import AppState
from netcore.tui.theme import (
    ACCENT_AMBER,
    ACCENT_GREEN,
    ACCENT_RED,
    BG_HEADER,
    BG_ROW_FOCUS,
    TEXT_MUTED,
    TEXT_ON_AMBER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def render(state: AppState) -> RenderableType:
    """Render the active modal, centred over a blank body."""
    modal = state.modal
    if modal is None:
        return Text("")
    table = Table.grid(expand=False)
    table.add_column(width=1, no_wrap=True)
    table.add_column(width=66, no_wrap=True)
    body: list[RenderableType] = [
        Text(f" {modal.title}", style=f"bold {TEXT_PRIMARY} on {BG_HEADER}")
    ]
    if modal.help_text:
        body.append(Text(f" {modal.help_text}", style=TEXT_MUTED))
    if modal.fields:
        for index, field in enumerate(modal.fields):
            focused = index == modal.cursor
            label = Text(f" {field:<20}", style=TEXT_SECONDARY)
            value = modal.values[index] if index < len(modal.values) else ""
            value_text = Text(
                f" {value or ' '} ",
                style=(
                    f"bold {TEXT_ON_AMBER} on {ACCENT_AMBER}"
                    if focused
                    else f"{TEXT_PRIMARY} on {BG_ROW_FOCUS}"
                ),
            )
            line = Table.grid(expand=True)
            line.add_column(width=22, no_wrap=True)
            line.add_column(ratio=1, no_wrap=True)
            line.add_row(label, value_text)
            body.append(line)
    if modal.body:
        for line in modal.body.splitlines():
            body.append(Text(f" {line}", style=TEXT_SECONDARY))
    if modal.error:
        body.append(Text(f" ✖ {modal.error}", style=f"bold {ACCENT_RED}"))
    footer = (
        " ↑↓ field   ↵ submit   esc cancel" if modal.fields else " esc close   ? help"
    )
    body.append(Text(footer, style=TEXT_MUTED))
    body.append(Text(f" {modal.submit}" if modal.submit else "", style=ACCENT_GREEN))
    table.add_row(Text("█", style=ACCENT_AMBER), Group(*body))
    return Align.center(table, vertical="middle")
