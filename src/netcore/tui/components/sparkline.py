"""Utilization bars and Unicode sparklines."""

from __future__ import annotations

from rich.text import Text

from netcore.tui.theme import utilization_style


def utilization_bar(pct: float, width: int = 10) -> str:
    """Render ``████░░░░░░`` for a percentage."""
    filled = max(0, min(width, round(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def utilization_text(pct: float, width: int = 10) -> Text:
    """Bar + percentage with threshold colour."""
    return Text(
        f"{utilization_bar(pct, width)} {pct:5.1f} %",
        style=utilization_style(pct),
    )


def sparkline_text(samples: str) -> Text:
    """Colour a precomputed sparkline string."""
    return Text(samples or "▁▁▁▁▁▁▁▁▁▁", style="#60a5fa")
