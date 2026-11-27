"""OpenCode flat dark palette (DEC-018)."""

from __future__ import annotations

from rich.style import Style
from rich.theme import Theme

BG_BASE = "#0f1117"
BG_HEADER = "#161922"
BG_SIDEBAR = "#0f1117"
BG_NAV_ACTIVE = "#1e2330"
BG_BTN_IDLE = "#1a1e29"
BG_BTN_FOCUS = "#f5a623"
BG_BTN_DANGER = "#1c171b"
BG_TOAST = "#1c212c"
BG_ROW_FOCUS = "#1b2130"
DIVIDER = "#232732"
TEXT_PRIMARY = "#e5e7eb"
TEXT_SECONDARY = "#9ca3af"
TEXT_MUTED = "#6b7280"
TEXT_ON_AMBER = "#0f1117"
ACCENT_GREEN = "#84cc16"
ACCENT_AMBER = "#f5a623"
ACCENT_RED = "#f87171"
ACCENT_BLUE = "#60a5fa"
ACCENT_PURPLE = "#a78bfa"

OPENCODE_THEME = Theme(
    {
        "netcore.bg": f"on {BG_BASE}",
        "netcore.header": f"{TEXT_PRIMARY} on {BG_HEADER}",
        "netcore.muted": TEXT_MUTED,
        "netcore.secondary": TEXT_SECONDARY,
        "netcore.primary": TEXT_PRIMARY,
        "netcore.green": ACCENT_GREEN,
        "netcore.amber": ACCENT_AMBER,
        "netcore.red": ACCENT_RED,
        "netcore.blue": ACCENT_BLUE,
        "netcore.purple": ACCENT_PURPLE,
    }
)


def severity_style(severity: str) -> Style:
    """Map an event severity to a Rich style."""
    mapping = {
        "DEBUG": TEXT_MUTED,
        "INFO": ACCENT_BLUE,
        "WARNING": ACCENT_AMBER,
        "ERROR": ACCENT_RED,
        "CRITICAL": ACCENT_RED,
    }
    return Style(color=mapping.get(severity, TEXT_SECONDARY))


def status_style(status: str) -> Style:
    """Map a device status to a Rich style."""
    mapping = {
        "ONLINE": ACCENT_GREEN,
        "OFFLINE": ACCENT_RED,
        "MAINTENANCE": ACCENT_AMBER,
    }
    return Style(color=mapping.get(status, TEXT_SECONDARY))


def utilization_style(pct: float) -> Style:
    """Colour utilization thresholds."""
    if pct > 90:
        return Style(color=ACCENT_RED)
    if pct >= 70:
        return Style(color=ACCENT_AMBER)
    return Style(color=ACCENT_GREEN)


def status_glyph(status: str) -> str:
    """Text paired with colour so status is never colour-only."""
    return {
        "ONLINE": "● online",
        "OFFLINE": "○ offline",
        "MAINTENANCE": "◐ maint",
    }.get(status, status.lower())
