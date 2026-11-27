"""Grouped OpenCode navigation rail."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text

from netcore.tui.state import GROUPS, NAV_ITEMS, AppState, FocusZone
from netcore.tui.theme import (
    ACCENT_AMBER,
    BG_NAV_ACTIVE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def render(state: AppState, width: int = 24) -> RenderableType:
    """Render the grouped sidebar with a full-width active row."""
    lines: list[Text] = []
    for group in GROUPS:
        if group != GROUPS[0]:
            lines.append(Text(""))
        lines.append(Text(f"  {group}", style=TEXT_MUTED))
        for item in NAV_ITEMS:
            if item.group != group:
                continue
            active = item.id == state.active
            if active:
                prefix = "▌ " if state.focus is FocusZone.SIDEBAR else "  "
                label = f" {prefix}{item.label}"
                padded = label.ljust(max(1, width - 1))
                lines.append(
                    Text(
                        padded,
                        style=f"bold {TEXT_PRIMARY} on {BG_NAV_ACTIVE}",
                    )
                )
                if state.focus is FocusZone.SIDEBAR:
                    lines[-1].stylize(ACCENT_AMBER, 1, 2)
            else:
                lines.append(Text(f"  {item.label}", style=TEXT_SECONDARY))
    return Group(*lines)
