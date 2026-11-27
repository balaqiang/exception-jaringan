"""Horizontal flat action buttons."""

from __future__ import annotations

from rich.text import Text

from netcore.tui.state import Action, FocusZone
from netcore.tui.theme import (
    ACCENT_RED,
    BG_BTN_DANGER,
    BG_BTN_FOCUS,
    BG_BTN_IDLE,
    TEXT_ON_AMBER,
    TEXT_PRIMARY,
)


def render(
    actions: tuple[Action, ...],
    state: FocusZone,
    selected: int,
) -> Text:
    """Render buttons separated by one space, amber on focus."""
    line = Text(" ")
    for index, action in enumerate(actions):
        focused = state is FocusZone.ACTIONS and index == selected
        if focused:
            style = f"bold {TEXT_ON_AMBER} on {BG_BTN_FOCUS}"
        elif action.kind == "danger":
            style = f"{ACCENT_RED} on {BG_BTN_DANGER}"
        else:
            style = f"{TEXT_PRIMARY} on {BG_BTN_IDLE}"
        line.append(f"  {action.label}  ", style=style)
        if index < len(actions) - 1:
            line.append(" ")
    return line
