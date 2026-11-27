"""Top status bar."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from netcore.tui.state import AppState
from netcore.tui.theme import (
    ACCENT_AMBER,
    ACCENT_GREEN,
    BG_HEADER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def render(state: AppState) -> RenderableType:
    """One-line brand + live telemetry."""
    snapshot = state.snapshot
    table = Table(
        expand=True,
        box=None,
        show_header=False,
        padding=(0, 1),
        style=f"on {BG_HEADER}",
    )
    table.add_column(ratio=1, no_wrap=True)
    table.add_column(justify="right", no_wrap=True)

    left = Text.assemble(
        (" NetCore", f"bold {TEXT_PRIMARY}"),
        (" • ", TEXT_MUTED),
        ("TUI", TEXT_SECONDARY),
    )
    right = Text()
    if state.paused:
        right.append("◐ paused", style=f"bold {ACCENT_AMBER}")
    else:
        right.append("● live", style=f"bold {ACCENT_GREEN}")
    if snapshot is not None:
        right.append("   devices ", style=TEXT_MUTED)
        right.append(
            str(snapshot.device_counts.get("total", 0)), style=f"bold {TEXT_PRIMARY}"
        )
        right.append("   links ", style=TEXT_MUTED)
        right.append(
            str(snapshot.link_counts.get("up", 0)), style=f"bold {TEXT_PRIMARY}"
        )
        right.append("/", style=TEXT_MUTED)
        right.append(
            str(snapshot.link_counts.get("total", 0)), style=f"bold {TEXT_PRIMARY}"
        )
        right.append("   db WAL ", style=TEXT_MUTED)
        right.append(
            f"v{snapshot.db_health.data_version}", style=f"bold {TEXT_PRIMARY}"
        )
    else:
        right.append("   db connecting…", style=TEXT_MUTED)
    table.add_row(left, right)
    return table
