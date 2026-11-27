"""TUI application state and navigation model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from netcore.application.dto import RealtimeMonitorSnapshotDTO


class FocusZone(StrEnum):
    """Keyboard focus zones."""

    SIDEBAR = "SIDEBAR"
    ACTIONS = "ACTIONS"
    CONTENT = "CONTENT"
    MODAL = "MODAL"


@dataclass(frozen=True, slots=True)
class NavItem:
    """One sidebar entry."""

    id: str
    label: str
    group: str
    shortcut: str


@dataclass(frozen=True, slots=True)
class Action:
    """One flat action-bar button."""

    id: str
    label: str
    kind: str = "normal"


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("dashboard", "Dashboard", "OPERATIONS", "1"),
    NavItem("topology", "Topology", "OPERATIONS", "6"),
    NavItem("packet_lab", "Packet Lab", "OPERATIONS", "7"),
    NavItem("traffic", "Traffic Monitor", "OPERATIONS", "8"),
    NavItem("devices", "Devices", "CONFIGURATION", "2"),
    NavItem("ipam", "IPAM Subnets", "CONFIGURATION", "3"),
    NavItem("routing", "Routing Table", "CONFIGURATION", "4"),
    NavItem("switch_ports", "Switch Ports", "CONFIGURATION", "5"),
    NavItem("db_inspector", "SQLite Inspector", "DATABASE & LOGS", "d"),
    NavItem("events", "Event Logs", "DATABASE & LOGS", "9"),
    NavItem("settings", "Settings", "DATABASE & LOGS", "0"),
)

NAV_BY_ID = {item.id: item for item in NAV_ITEMS}
NAV_BY_SHORTCUT = {item.shortcut: item for item in NAV_ITEMS}

GROUPS: tuple[str, ...] = ("OPERATIONS", "CONFIGURATION", "DATABASE & LOGS")

SETTINGS_FIELDS: tuple[str, ...] = (
    "default_ttl",
    "default_link_capacity",
    "arp_timeout_s",
    "mac_timeout_s",
    "max_hops",
    "event_retention",
    "seed",
    "poll_interval_ms",
)

INSPECTOR_TABLES: tuple[str, ...] = (
    "devices",
    "interfaces",
    "links",
    "subnets",
    "routes",
    "arp_entries",
    "mac_entries",
    "events",
    "simulation_runs",
    "hop_records",
    "traffic_counters",
    "settings",
    "schema_migrations",
)


@dataclass(slots=True)
class ToastState:
    """Top-right notification card."""

    message: str
    severity: str = "info"
    subtitle: str = ""
    expires_at: float = 0.0


@dataclass(slots=True)
class ModalState:
    """Flat modal overlay."""

    kind: str
    title: str
    fields: tuple[str, ...] = ()
    values: list[str] = field(default_factory=list)
    cursor: int = 0
    submit: str = ""
    error: str | None = None
    help_text: str = ""
    body: str = ""

    @classmethod
    def form(
        cls,
        kind: str,
        title: str,
        fields: tuple[str, ...],
        values: list[str] | None = None,
        *,
        submit: str = "",
        help_text: str = "",
    ) -> ModalState:
        """Build an editable form modal."""
        return cls(
            kind=kind,
            title=title,
            fields=fields,
            values=values or ["" for _ in fields],
            submit=submit,
            help_text=help_text,
        )


@dataclass(slots=True)
class AppState:
    """All mutable view state; only the main thread touches it."""

    active: str = "dashboard"
    focus: FocusZone = FocusZone.SIDEBAR
    action_index: int = 0
    cursors: dict[str, int] = field(default_factory=dict)
    scrolls: dict[str, int] = field(default_factory=dict)
    search: str = ""
    filter_active: bool = False
    paused: bool = False
    toast: ToastState | None = None
    modal: ModalState | None = None
    elapsed_seconds: int = 0
    snapshot: RealtimeMonitorSnapshotDTO | None = None
    data: dict[str, Any] = field(default_factory=dict)
    show_sidebar: bool | None = None
    list_mode: bool = False
    last_path: tuple[int, ...] = ()
    status_line: str = ""
    inspector_table: str = "devices"
    inspector_offset: int = 0
    inspector_sort: str | None = None
    inspector_desc: bool = True

    def focus_actions(self) -> None:
        """Convenience for tests and programmatic actions."""
        self.focus = FocusZone.ACTIONS

    @classmethod
    def initial(cls) -> AppState:
        """Create the default state."""
        return cls()

    @property
    def nav(self) -> NavItem:
        """Active navigation entry."""
        return NAV_BY_ID.get(self.active, NAV_ITEMS[0])

    def cursor(self, key: str, length: int) -> int:
        """Clamp and return the cursor for a list."""
        if length <= 0:
            return 0
        value = max(0, min(self.cursors.get(key, 0), length - 1))
        self.cursors[key] = value
        return value

    def move_cursor(self, key: str, delta: int, length: int) -> None:
        """Move a cursor within bounds."""
        if length <= 0:
            self.cursors[key] = 0
            return
        self.cursors[key] = max(0, min(self.cursors.get(key, 0) + delta, length - 1))

    def set_toast(
        self, message: str, severity: str = "info", subtitle: str = ""
    ) -> None:
        """Show a toast for 4s (8s for errors)."""
        import time

        duration = 8.0 if severity == "error" else 4.0
        self.toast = ToastState(
            message=message,
            severity=severity,
            subtitle=subtitle,
            expires_at=time.monotonic() + duration,
        )
