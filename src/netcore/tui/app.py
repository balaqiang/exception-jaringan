"""Rich Live application loop (DEC-016)."""

from __future__ import annotations

import queue
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.table import Table
from rich.text import Text

from netcore.application.container import ServiceContainer
from netcore.application.dto import (
    AssignAddressRequest,
    ConnectRequest,
    CreateDeviceRequest,
    DeviceDTO,
    EventFilterDTO,
    FlowRequest,
    RealtimeMonitorSnapshotDTO,
    RouteRequest,
    SendPacketRequest,
    SettingsUpdateRequest,
    SubnetDTO,
    SubnetRequest,
    UpdateDeviceRequest,
)
from netcore.application.errors import ApplicationError, as_application_error
from netcore.application.ports import MonitorPoller
from netcore.tui.components import (
    action_bar,
    footer,
    header,
    kv_block,
    modal,
    sidebar,
    status_strip,
    toast,
)
from netcore.tui.input_handler import KeyEvent, RawKeyboardReader
from netcore.tui.layout import (
    COLLAPSE_WIDTH,
    MIN_HEIGHT,
    MIN_WIDTH,
    build_body,
    build_root,
    divider_text,
    pad_workspace,
    too_small,
)
from netcore.tui.state import (
    INSPECTOR_TABLES,
    NAV_ITEMS,
    SETTINGS_FIELDS,
    AppState,
    FocusZone,
    ModalState,
)
from netcore.tui.theme import OPENCODE_THEME, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY
from netcore.tui.views import VIEWS

SEVERITIES: tuple[str | None, ...] = (None, "WARNING", "ERROR", "INFO")
CATEGORIES: tuple[str | None, ...] = (
    None,
    "CONFIG",
    "STATE",
    "DROP",
    "DELIVERY",
    "TRAFFIC",
    "SYSTEM",
)


@dataclass(frozen=True, slots=True)
class UiMessage:
    """Base class for thread -> UI messages."""


@dataclass(frozen=True, slots=True)
class SnapshotReady(UiMessage):
    """A new analytics snapshot."""

    snapshot: RealtimeMonitorSnapshotDTO


@dataclass(frozen=True, slots=True)
class ActionCompleted(UiMessage):
    """A background action finished."""

    message: str
    severity: str = "info"
    subtitle: str = ""


class RichLiveApp:
    """OpenCode-style Rich Live terminal application."""

    def __init__(
        self,
        services: ServiceContainer,
        watcher: MonitorPoller,
        reader: object | None = None,
        console: Console | None = None,
    ) -> None:
        self._services = services
        self._watcher = watcher
        self._reader = reader
        self._console = console or Console(theme=OPENCODE_THEME)
        self._state = AppState.initial()
        self._ui_queue: queue.Queue[UiMessage] = queue.Queue()
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="netcore-ui"
        )
        self._running = False
        self._started_at = time.monotonic()
        self._last_tick = 0.0
        self._last_tail = 0.0
        self._poll_configured = False

    # ------------------------------------------------------------------ props
    @property
    def state(self) -> AppState:
        """Expose state for headless tests."""
        return self._state

    @property
    def active_view(self) -> str:
        """Active view id."""
        return self._state.active

    def prepare(self) -> None:
        """Load the active view and one synchronous snapshot (headless/tests)."""
        self._load_view(self._state.active)
        self.prime_snapshot()

    def prime_snapshot(self) -> RealtimeMonitorSnapshotDTO:
        """Fetch one analytics snapshot without starting the watcher thread."""
        snapshot = self._services.analytics.snapshot(
            active_table=(
                self._state.inspector_table
                if self._state.active == "db_inspector"
                else None
            ),
            table_search=self._state.search,
            table_sort_by=self._state.inspector_sort,
            table_descending=self._state.inspector_desc,
            table_offset=self._state.inspector_offset,
            table_limit=50,
        )
        self._state.snapshot = snapshot
        return snapshot

    # -------------------------------------------------------------------- run
    def run(self) -> None:
        """Start the watcher, enter the alternate screen, run the loop."""
        self._running = True
        self._started_at = time.monotonic()
        self._load_view(self._state.active)
        self._sync_watcher_query()
        self._watcher.start(self._on_snapshot)
        try:
            with (
                RawKeyboardReader() as keyboard,
                Live(
                    self.render(),
                    console=self._console,
                    screen=True,
                    auto_refresh=False,
                    refresh_per_second=15,
                ) as live,
            ):
                last_size = self._console.size
                while self._running:
                    dirty = False
                    key = keyboard.read_key(timeout_s=0.04)
                    if key is not None:
                        dirty |= self.handle_key(key)
                    dirty |= self._drain_queue()
                    dirty |= self._tick()
                    if self._console.size != last_size:
                        last_size = self._console.size
                        dirty = True
                    if dirty:
                        live.update(self.render(), refresh=True)
        finally:
            self._watcher.stop()
            self._executor.shutdown(wait=False, cancel_futures=True)
            closer = getattr(self._reader, "close", None)
            if closer is not None:
                closer()

    # --------------------------------------------------------------- rendering
    def render(
        self, width: int | None = None, height: int | None = None
    ) -> RenderableType:
        """Build the current frame."""
        width = width or self._console.size.width
        height = height or self._console.size.height
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            return too_small(width, height)
        state = self._state
        view = VIEWS[state.active]
        content = view.build(state)
        actions = view.actions(state)
        sidebar_visible = self._sidebar_effective(width)

        title_table = Table(expand=True, box=None, show_header=False, padding=0)
        title_table.add_column(ratio=1, no_wrap=True)
        title_table.add_column(width=34, no_wrap=True)
        title = Group(
            Text(view.title, style=f"bold {TEXT_PRIMARY}"),
            Text(view.subtitle, style=TEXT_SECONDARY),
        )
        title_table.add_row(title, toast.render(state))

        workspace_body: list[RenderableType] = [
            title_table,
            action_bar.render(actions, state.focus, state.action_index),
            status_strip.render(state, self._status_meta()),
            kv_block.render(content.metrics),
            Text(""),
        ]
        if state.modal is not None:
            workspace_body.append(modal.render(state))
        else:
            workspace_body.append(Text(f"  {content.section}", style=TEXT_MUTED))
            workspace_body.append(content.body)
        workspace = pad_workspace(Group(*workspace_body))
        body = build_body(
            sidebar.render(state),
            divider_text(height - 2),
            workspace,
            show_sidebar=sidebar_visible,
        )
        root = build_root(
            header.render(state),
            body,
            footer.render(state),
        )
        root.name = "root"
        return root

    def _sidebar_effective(self, width: int) -> bool:
        if self._state.show_sidebar is None:
            return width >= COLLAPSE_WIDTH
        return self._state.show_sidebar

    def _status_meta(self) -> str:
        snapshot = self._state.snapshot
        if snapshot is None:
            return "sqlite connecting…"
        return (
            f"sqlite WAL · {snapshot.link_counts.get('total', 0)} links · "
            f"{snapshot.db_health.last_poll_ms:.1f} ms poll · "
            f"{snapshot.db_health.total_rows:,} rows"
        )

    # ---------------------------------------------------------------- messages
    def _on_snapshot(self, snapshot: RealtimeMonitorSnapshotDTO) -> None:
        self._ui_queue.put(SnapshotReady(snapshot))

    def _drain_queue(self) -> bool:
        dirty = False
        while True:
            try:
                message = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(message, SnapshotReady):
                previous = self._state.data.get("last_total_rows")
                if previous is not None:
                    delta = message.snapshot.db_health.total_rows - int(previous)
                    pulse = self._state.data.setdefault("db_pulse", [])
                    pulse.append(delta)
                    del pulse[:-12]
                    self._state.data["db_delta"] = delta
                self._state.data["last_total_rows"] = (
                    message.snapshot.db_health.total_rows
                )
                self._state.snapshot = message.snapshot
                if (
                    self._state.active == "db_inspector"
                    and message.snapshot.active_table_page is None
                ):
                    self._sync_watcher_query()
                dirty = True
            elif isinstance(message, ActionCompleted):
                self._state.set_toast(
                    message.message, message.severity, message.subtitle
                )
                dirty = True
        return dirty

    def _tick(self) -> bool:
        now = time.monotonic()
        dirty = False
        elapsed = int(now - self._started_at)
        if elapsed != self._state.elapsed_seconds:
            self._state.elapsed_seconds = elapsed
            dirty = True
        toast_state = self._state.toast
        if toast_state is not None and now >= toast_state.expires_at:
            self._state.toast = None
            dirty = True
        if now - self._last_tick >= 1.0:
            self._last_tick = now
            if (
                self._state.active == "events"
                and self._state.data.get("tail")
                and now - self._last_tail >= 1.0
            ):
                self._last_tail = now
                self._load_events()
                dirty = True
        return dirty

    # ------------------------------------------------------------------ input
    def handle_key(self, key: KeyEvent) -> bool:
        """Dispatch one key press."""
        state = self._state
        if key.kind == "CTRL_C":
            self._running = False
            return True
        if state.modal is not None:
            return self._handle_modal(key)
        if state.filter_active:
            return self._handle_filter(key)
        if key.kind == "CHAR":
            char = key.char.lower()
            if char == "q":
                self._running = False
                return True
            mapping = {
                "1": "dashboard",
                "2": "devices",
                "3": "ipam",
                "4": "routing",
                "5": "switch_ports",
                "6": "topology",
                "7": "packet_lab",
                "8": "traffic",
                "9": "events",
                "0": "settings",
                "d": "db_inspector",
            }
            if char in mapping:
                self._switch_view(mapping[char])
                return True
            if char == "?":
                self._open_help()
                return True
            if char == "/":
                state.filter_active = True
                state.search = ""
                state.inspector_offset = 0
                return True
            if char == " ":
                state.paused = self._watcher.toggle()
                return True
            if char == "r":
                self._refresh_all()
                return True
        if key.kind in {"TAB", "SHIFT_TAB"}:
            self._cycle_focus(1 if key.kind == "TAB" else -1)
            return True
        if key.kind == "CTRL_B":
            state.show_sidebar = not self._sidebar_effective(self._console.size.width)
            return True
        if key.kind == "ESC":
            if state.focus is FocusZone.CONTENT:
                state.focus = FocusZone.ACTIONS
            elif state.focus is FocusZone.ACTIONS:
                state.focus = FocusZone.SIDEBAR
            return True
        if state.focus is FocusZone.SIDEBAR:
            return self._handle_sidebar(key)
        if state.focus is FocusZone.ACTIONS:
            return self._handle_actions(key)
        if state.focus is FocusZone.CONTENT:
            return self._handle_content(key)
        return False

    def _handle_sidebar(self, key: KeyEvent) -> bool:
        state = self._state
        if key.kind in {"UP", "DOWN", "CHAR"}:
            if key.kind == "CHAR":
                if key.char.lower() == "k":
                    delta = -1
                elif key.char.lower() == "j":
                    delta = 1
                else:
                    return False
            else:
                delta = -1 if key.kind == "UP" else 1
            ids = [item.id for item in NAV_ITEMS]
            index = ids.index(state.active) if state.active in ids else 0
            self._switch_view(ids[max(0, min(len(ids) - 1, index + delta))])
            return True
        if key.kind in {"RIGHT", "ENTER"}:
            state.focus = (
                FocusZone.ACTIONS
                if VIEWS[state.active].actions(state)
                else FocusZone.CONTENT
            )
            return True
        return False

    def _handle_actions(self, key: KeyEvent) -> bool:
        state = self._state
        actions = VIEWS[state.active].actions(state)
        if not actions:
            if key.kind == "DOWN":
                state.focus = FocusZone.CONTENT
                return True
            return False
        if key.kind == "LEFT":
            state.action_index = max(0, state.action_index - 1)
            return True
        if key.kind == "RIGHT":
            state.action_index = min(len(actions) - 1, state.action_index + 1)
            return True
        if key.kind == "UP":
            state.focus = FocusZone.SIDEBAR
            return True
        if key.kind == "DOWN":
            state.focus = FocusZone.CONTENT
            return True
        if key.kind == "ENTER":
            self._execute_action(actions[state.action_index].id)
            return True
        return False

    def _handle_content(self, key: KeyEvent) -> bool:
        state = self._state
        view = VIEWS[state.active]
        if view.handle_key(key, state):
            self._after_cursor_move()
            return True
        if key.kind == "ENTER":
            return self._content_enter()
        if key.kind in {"UP", "DOWN"}:
            return False
        if key.kind == "ESC":
            state.focus = FocusZone.ACTIONS
            return True
        return False

    def _cycle_focus(self, delta: int) -> None:
        order = [FocusZone.SIDEBAR, FocusZone.ACTIONS, FocusZone.CONTENT]
        state = self._state
        index = order.index(state.focus) if state.focus in order else 0
        state.focus = order[(index + delta) % len(order)]

    def _handle_filter(self, key: KeyEvent) -> bool:
        state = self._state
        if key.kind == "ESC":
            state.filter_active = False
            state.search = ""
            self._apply_filter()
            return True
        if key.kind == "ENTER":
            state.filter_active = False
            self._apply_filter()
            return True
        if key.kind == "BACKSPACE":
            state.search = state.search[:-1]
            self._apply_filter()
            return True
        if key.kind == "CHAR":
            state.search += key.char
            self._apply_filter()
            return True
        return False

    def _apply_filter(self) -> None:
        state = self._state
        if state.active == "db_inspector":
            state.inspector_offset = 0
            self._sync_watcher_query()
        elif state.active == "events":
            self._load_events()
        elif state.active == "devices":
            self._load_devices()

    def _handle_modal(self, key: KeyEvent) -> bool:
        state = self._state
        modal_state = state.modal
        assert modal_state is not None
        if key.kind == "ESC":
            state.modal = None
            return True
        if modal_state.fields:
            if key.kind in {"TAB", "DOWN"}:
                modal_state.cursor = (modal_state.cursor + 1) % len(modal_state.fields)
                return True
            if key.kind == "UP":
                modal_state.cursor = (modal_state.cursor - 1) % len(modal_state.fields)
                return True
            if key.kind == "BACKSPACE":
                value = modal_state.values[modal_state.cursor]
                modal_state.values[modal_state.cursor] = value[:-1]
                return True
            if key.kind == "CHAR":
                modal_state.values[modal_state.cursor] += key.char
                return True
        if key.kind == "ENTER":
            self._submit_modal()
            return True
        return False

    # --------------------------------------------------------------- navigation
    def _switch_view(self, view_id: str) -> None:
        state = self._state
        if view_id not in VIEWS:
            return
        state.active = view_id
        state.action_index = 0
        state.search = ""
        self._load_view(view_id)
        self._sync_watcher_query()

    def _load_view(self, view_id: str) -> None:
        loaders = {
            "dashboard": lambda: None,
            "devices": self._load_devices,
            "ipam": self._load_ipam,
            "routing": self._load_routing,
            "switch_ports": self._load_switches,
            "topology": self._load_topology,
            "packet_lab": self._load_packet_lab,
            "traffic": self._load_traffic,
            "events": self._load_events,
            "settings": self._load_settings,
            "db_inspector": lambda: None,
        }
        loader = loaders.get(view_id)
        if loader is None:
            return
        try:
            loader()
        except Exception as exc:
            self._error(exc)

    def _after_cursor_move(self) -> None:
        state = self._state
        try:
            if state.active == "devices":
                self._load_device_detail()
            elif state.active == "ipam":
                self._load_addresses()
        except Exception as exc:
            self._error(exc)

    # ------------------------------------------------------------- data loaders
    def _load_devices(self) -> None:
        devices = self._services.device.list_devices(search=self._state.search)
        self._state.data["devices"] = devices
        self._load_device_detail()

    def _load_device_detail(self) -> None:
        devices = self._state.data.get("devices", ()) or ()
        index = self._state.cursor("devices", len(devices))
        self._state.data["device_detail"] = (
            self._services.device.detail(devices[index].device_id) if devices else None
        )

    def _load_ipam(self) -> None:
        subnets = self._services.ipam.list_subnets()
        self._state.data["subnets"] = subnets
        self._load_addresses()

    def _load_addresses(self) -> None:
        subnets = self._state.data.get("subnets", ()) or ()
        index = self._state.cursor("ipam", len(subnets))
        self._state.data["addresses"] = (
            self._services.ipam.list_addresses(subnets[index].subnet_id)
            if subnets
            else ()
        )

    def _load_routing(self) -> None:
        routers = self._services.routing.routers()
        self._state.data["routers"] = routers
        index = int(self._state.data.get("router_index", 0) or 0)
        if routers:
            index %= len(routers)
        else:
            index = 0
        self._state.data["router_index"] = index
        self._state.data["routes"] = (
            self._services.routing.routes(routers[index].device_id) if routers else ()
        )

    def _load_switches(self) -> None:
        switches = self._services.switch.switches()
        self._state.data["switches"] = switches
        index = int(self._state.data.get("switch_index", 0) or 0)
        if switches:
            index %= len(switches)
        else:
            index = 0
        self._state.data["switch_index"] = index
        if switches:
            self._state.data["ports"] = self._services.switch.ports(
                switches[index].device_id
            )
            self._state.data["macs"] = self._services.switch.mac_table(
                switches[index].device_id
            )
        else:
            self._state.data["ports"] = ()
            self._state.data["macs"] = ()

    def _load_topology(self) -> None:
        self._state.data["topology"] = self._services.topology.snapshot(
            self._state.last_path
        )
        self._state.data["links"] = self._services.topology.links()

    def _load_packet_lab(self) -> None:
        self._state.data["devices"] = self._services.device.list_devices()
        self._resolve_default_destination()
        if "packet_mode" not in self._state.data:
            self._state.data["packet_mode"] = "trace"

    def _load_traffic(self) -> None:
        self._state.data["devices"] = self._services.device.list_devices()
        self._resolve_default_destination()
        self._state.data["flows"] = self._services.monitoring.flows()
        self._state.data["links"] = self._services.monitoring.link_stats()

    def _resolve_default_destination(self) -> None:
        source = self._default_source()
        types = {
            device.hostname: device.device_type
            for device in self._state.data.get("devices", ()) or ()
        }
        for subnet in self._services.ipam.list_subnets():
            for address in self._services.ipam.list_addresses(subnet.subnet_id):
                if (
                    address.ip
                    and address.device_name != source
                    and types.get(address.device_name) == "SERVER"
                ):
                    self._state.data["default_dst"] = address.ip
                    return
        self._state.data.setdefault("default_dst", "10.0.2.10")

    def _load_events(self) -> None:
        state = self._state
        severity = state.data.get("event_severity")
        category = state.data.get("event_category")
        events = self._services.event_log.query(
            EventFilterDTO(
                severity=severity,
                category=category,
                search=state.search,
            )
        )
        state.data["events"] = events
        state.data["event_total"] = str(len(events)) if events else "0"

    def _load_settings(self) -> None:
        settings = self._services.settings.get()
        self._state.data["settings"] = settings
        self._state.data["settings_values"] = {
            "default_ttl": str(settings.default_ttl),
            "default_link_capacity": str(settings.default_link_capacity),
            "arp_timeout_s": str(settings.arp_timeout_s),
            "mac_timeout_s": str(settings.mac_timeout_s),
            "max_hops": str(settings.max_hops),
            "event_retention": str(settings.event_retention),
            "seed": str(settings.seed),
            "poll_interval_ms": str(settings.poll_interval_ms),
        }
        if not self._poll_configured:
            self._watcher.set_interval(settings.poll_interval_ms / 1000)
            self._poll_configured = True

    def _refresh_all(self) -> None:
        self._watcher.refresh_now()
        self._load_view(self._state.active)
        self._state.set_toast("Refreshed from SQLite", "info")

    def _sync_watcher_query(self) -> None:
        state = self._state
        if state.active == "db_inspector":
            self._watcher.set_query(
                state.inspector_table,
                search=state.search,
                sort_by=state.inspector_sort,
                descending=state.inspector_desc,
                offset=state.inspector_offset,
                limit=50,
            )

    # --------------------------------------------------------------- actions
    def _actions(self) -> tuple[Any, ...]:
        return VIEWS[self._state.active].actions(self._state)

    def _execute_action(self, action_id: str) -> None:
        state = self._state
        handlers = {
            "pause": self._toggle_pause,
            "refresh": self._refresh_all,
            "sample_lab": lambda: self._load_lab("spine-leaf"),
            "reset_lab": lambda: self._confirm(
                "confirm_reset_lab",
                "Reset lab",
                "This removes every device, link, subnet and route.",
                "Reset Lab",
            ),
            "switch_table": self._cycle_inspector,
            "sort_desc": self._toggle_sort,
            "col_stats": self._show_column_stats,
            "export_csv": lambda: self._open_export("export_table"),
            "tail": self._toggle_tail,
            "cycle_severity": self._cycle_severity,
            "cycle_category": self._cycle_category,
            "export_events": lambda: self._open_export("export_events"),
            "new_device": self._open_new_device,
            "edit_device": self._open_edit_device,
            "cycle_status": self._cycle_status,
            "delete_device": lambda: self._confirm(
                "confirm_delete_device",
                "Delete device",
                "Links and routes attached to this device will be removed.",
                "Delete",
            ),
            "new_subnet": self._open_new_subnet,
            "assign_ip": self._open_assign_ip,
            "release_ip": self._release_ip,
            "delete_subnet": self._delete_subnet,
            "switch_router": self._switch_router,
            "add_route": self._open_add_route,
            "lpm_lookup": self._open_lpm,
            "delete_route": self._delete_route,
            "switch_device": self._switch_device,
            "toggle_port": self._toggle_port,
            "edit_port": self._open_edit_port,
            "clear_macs": self._clear_macs,
            "add_link": self._open_add_link,
            "toggle_link": self._toggle_link,
            "highlight_path": self._toggle_path,
            "list_mode": self._toggle_list_mode,
            "send_packet": lambda: self._open_packet("send_packet"),
            "traceroute": lambda: self._open_packet("traceroute"),
            "history": self._show_history,
            "clear_result": self._clear_result,
            "start_flow": self._open_flow,
            "stop_flow": self._stop_flow,
            "reset_counters": lambda: self._confirm(
                "confirm_reset_counters",
                "Reset counters",
                "Every active flow is stopped and traffic counters are cleared.",
                "Reset",
            ),
            "save_settings": self._save_settings,
            "load_spine": lambda: self._load_lab("spine-leaf"),
            "load_two": lambda: self._load_lab("two-router"),
        }
        handler = handlers.get(action_id)
        if handler is None:
            state.set_toast(f"Action {action_id} is not wired", "warning")
            return
        try:
            handler()
        except Exception as exc:
            self._error(exc)

    def _toggle_pause(self) -> None:
        self._state.paused = self._watcher.toggle()
        self._state.set_toast(
            "Polling paused" if self._state.paused else "Polling resumed",
            "warning" if self._state.paused else "info",
        )

    def _load_lab(self, name: str) -> None:
        self._services.settings.load_sample_lab(name)
        self._state.last_path = ()
        self._watcher.refresh_now()
        self._load_view(self._state.active)
        self._state.set_toast(f"Lab '{name}' loaded", "success")

    def _cycle_inspector(self) -> None:
        state = self._state
        index = INSPECTOR_TABLES.index(state.inspector_table)
        state.inspector_table = INSPECTOR_TABLES[(index + 1) % len(INSPECTOR_TABLES)]
        state.inspector_offset = 0
        state.cursors["db_rows"] = 0
        self._sync_watcher_query()

    def _toggle_sort(self) -> None:
        state = self._state
        if state.inspector_sort is None:
            page = state.snapshot.active_table_page if state.snapshot else None
            state.inspector_sort = page.columns[0] if page and page.columns else "id"
        state.inspector_desc = not state.inspector_desc
        self._sync_watcher_query()
        self._state.set_toast(
            "Sort descending" if state.inspector_desc else "Sort ascending", "info"
        )

    def _show_column_stats(self) -> None:
        snapshot = self._state.snapshot
        page = snapshot.active_table_page if snapshot else None
        if page is None:
            self._state.set_toast("No table page loaded yet", "warning")
            return
        lines = [
            f"{page.table_name}: {page.filtered_rows} rows, {page.query_ms:.1f} ms"
        ]
        for stat in page.column_stats:
            lines.append(
                f"{stat.column:<18} {stat.dtype:<10} non-null {stat.non_null_count:<5} "
                f"null {stat.null_count:<4} unique {stat.unique_count:<5} "
                f"min {stat.min_val or '—'} max {stat.max_val or '—'}"
            )
            if stat.mean_val is not None:
                lines.append(
                    f"{'':<18} mean {stat.mean_val:,.2f}  p50 {stat.p50_val:,.2f}  "
                    f"p95 {stat.p95_val:,.2f}"
                )
        self._state.modal = ModalState(
            kind="detail",
            title="Pandas column statistics",
            body="\n".join(lines[:22]),
            submit="",
        )

    def _open_export(self, kind: str) -> None:
        default = (
            f"{self._state.inspector_table}.csv"
            if kind == "export_table"
            else "events.csv"
        )
        self._state.modal = ModalState.form(
            kind,
            "Export data",
            ("path",),
            [default],
            help_text="CSV or JSON extension; parent folders are created.",
        )

    def _toggle_tail(self) -> None:
        state = self._state
        state.data["tail"] = not state.data.get("tail")
        state.set_toast(
            "Live tail enabled" if state.data["tail"] else "Live tail disabled",
            "info",
        )
        self._load_events()

    def _cycle_severity(self) -> None:
        state = self._state
        current = state.data.get("event_severity")
        index = SEVERITIES.index(current) if current in SEVERITIES else 0
        state.data["event_severity"] = SEVERITIES[(index + 1) % len(SEVERITIES)]
        self._load_events()

    def _cycle_category(self) -> None:
        state = self._state
        current = state.data.get("event_category")
        index = CATEGORIES.index(current) if current in CATEGORIES else 0
        state.data["event_category"] = CATEGORIES[(index + 1) % len(CATEGORIES)]
        self._load_events()

    def _selected_device(self) -> DeviceDTO | None:
        devices = self._state.data.get("devices", ()) or ()
        if not devices:
            return None
        return devices[self._state.cursor("devices", len(devices))]

    def _selected_subnet(self) -> SubnetDTO | None:
        subnets = self._state.data.get("subnets", ()) or ()
        if not subnets:
            return None
        return subnets[self._state.cursor("ipam", len(subnets))]

    def _selected_router(self) -> DeviceDTO | None:
        routers = self._state.data.get("routers", ()) or ()
        if not routers:
            return None
        index = int(self._state.data.get("router_index", 0) or 0) % len(routers)
        return routers[index]

    def _selected_switch(self) -> DeviceDTO | None:
        switches = self._state.data.get("switches", ()) or ()
        if not switches:
            return None
        index = int(self._state.data.get("switch_index", 0) or 0) % len(switches)
        return switches[index]

    def _open_new_device(self) -> None:
        self._state.modal = ModalState.form(
            "device_new",
            "New device",
            (
                "hostname",
                "type (ROUTER/SWITCH/SERVER)",
                "interfaces",
                "location",
                "description",
            ),
            ["core-1", "ROUTER", "4", "DC-1", ""],
        )

    def _open_edit_device(self) -> None:
        device = self._selected_device()
        if device is None:
            self._state.set_toast("No device selected", "warning")
            return
        self._state.modal = ModalState.form(
            "device_edit",
            f"Edit {device.hostname}",
            ("hostname", "location", "description"),
            [device.hostname, device.location, device.description],
        )

    def _cycle_status(self) -> None:
        device = self._selected_device()
        if device is None:
            return
        self._services.device.cycle_status(device.device_id)
        self._load_devices()
        self._state.set_toast(f"{device.hostname} status cycled", "info")

    def _open_new_subnet(self) -> None:
        self._state.modal = ModalState.form(
            "subnet_new",
            "New subnet",
            ("cidr", "name", "gateway"),
            ["10.20.0.0/24", "new-lan", "10.20.0.1"],
        )

    def _open_assign_ip(self) -> None:
        device = self._selected_device()
        subnet = self._selected_subnet()
        next_ip = ""
        if subnet is not None:
            try:
                next_ip = self._services.ipam.next_free_address(subnet.subnet_id) or ""
            except ApplicationError:
                next_ip = ""
        if device is None:
            devices = self._services.device.list_devices()
            device = next(iter(devices), None)
        if device is None:
            self._state.set_toast("Create a device first", "warning")
            return
        self._state.modal = ModalState.form(
            "assign_ip",
            "Assign address",
            ("device hostname", "interface", "address/prefix"),
            [device.hostname, "eth0", next_ip],
        )

    def _release_ip(self) -> None:
        addresses = self._state.data.get("addresses", ()) or ()
        if not addresses:
            self._state.set_toast("No address selected", "warning")
            return
        target = addresses[0]
        self._services.ipam.release_address(target.device_id, target.name)
        self._load_ipam()
        self._state.set_toast(f"Released {target.ip}/{target.prefix_len}", "warning")

    def _delete_subnet(self) -> None:
        subnet = self._selected_subnet()
        if subnet is None:
            return
        self._services.ipam.delete_subnet(subnet.subnet_id)
        self._load_ipam()
        self._state.set_toast(f"Subnet {subnet.cidr} deleted", "warning")

    def _switch_router(self) -> None:
        routers = self._state.data.get("routers", ()) or ()
        if not routers:
            return
        self._state.data["router_index"] = (
            int(self._state.data.get("router_index", 0) or 0) + 1
        ) % len(routers)
        self._load_routing()
        router = self._selected_router()
        self._state.set_toast(f"Router {router.hostname if router else 'none'}", "info")

    def _open_add_route(self) -> None:
        router = self._selected_router()
        if router is None:
            self._state.set_toast("No router available", "warning")
            return
        self._state.modal = ModalState.form(
            "route_new",
            f"Add route on {router.hostname}",
            ("destination", "next hop", "interface", "metric"),
            ["10.99.0.0/24", "", "ge0/0", "0"],
        )

    def _open_lpm(self) -> None:
        self._state.modal = ModalState.form(
            "lpm_lookup",
            "Longest-prefix lookup",
            ("destination ip",),
            ["10.20.0.5"],
        )

    def _delete_route(self) -> None:
        router = self._selected_router()
        routes = self._state.data.get("routes", ()) or ()
        if router is None or not routes:
            self._state.set_toast("No route selected", "warning")
            return
        route = routes[self._state.cursor("routing", len(routes))]
        if route.route_type == "CONNECTED":
            self._state.set_toast("Connected routes are read-only", "warning")
            return
        self._services.routing.remove_route(router.device_id, route.route_id)
        self._load_routing()
        self._state.set_toast("Route removed", "warning")

    def _switch_device(self) -> None:
        switches = self._state.data.get("switches", ()) or ()
        if not switches:
            return
        self._state.data["switch_index"] = (
            int(self._state.data.get("switch_index", 0) or 0) + 1
        ) % len(switches)
        self._load_switches()
        switch = self._selected_switch()
        self._state.set_toast(f"Switch {switch.hostname if switch else 'none'}", "info")

    def _toggle_port(self) -> None:
        switch = self._selected_switch()
        ports = self._state.data.get("ports", ()) or ()
        if switch is None or not ports:
            return
        port = ports[self._state.cursor("ports", len(ports))]
        self._services.switch.set_port_admin(
            switch.device_id, port.number, not port.admin_up
        )
        self._load_switches()
        self._state.set_toast(f"Port {port.number} toggled", "info")

    def _open_edit_port(self) -> None:
        switch = self._selected_switch()
        ports = self._state.data.get("ports", ()) or ()
        if switch is None or not ports:
            return
        port = ports[self._state.cursor("ports", len(ports))]
        self._state.modal = ModalState.form(
            "port_edit",
            f"{switch.hostname} port {port.number}",
            ("speed Mbps", "description"),
            [str(port.speed_mbps), port.description],
        )

    def _clear_macs(self) -> None:
        switch = self._selected_switch()
        if switch is None:
            return
        self._services.switch.clear_mac_table(switch.device_id)
        self._load_switches()
        self._state.set_toast("MAC table cleared", "warning")

    def _open_add_link(self) -> None:
        topology = self._state.data.get("topology")
        if topology is None or len(topology.nodes) < 2:
            self._state.set_toast("Need at least two devices", "warning")
            return
        first, second = topology.nodes[0], topology.nodes[1]
        self._state.modal = ModalState.form(
            "link_new",
            "Add link",
            ("device a", "interface a", "device b", "interface b", "capacity Mbps"),
            [first.hostname, "ge0/0", second.hostname, "ge0/0", "1000"],
        )

    def _toggle_link(self) -> None:
        links = self._state.data.get("links", ()) or ()
        if not links:
            return
        link = links[self._state.cursor("topology", len(links))]
        self._services.topology.set_link_admin(link.link_id, not link.admin_up)
        self._load_topology()
        self._state.set_toast(f"Link {link.link_id} toggled", "info")

    def _toggle_path(self) -> None:
        state = self._state
        state.data["highlight"] = not state.data.get("highlight", True)
        if not state.data["highlight"]:
            state.last_path = ()
        elif state.data.get("last_result_ids"):
            state.last_path = tuple(state.data["last_result_ids"])
        self._load_topology()

    def _toggle_list_mode(self) -> None:
        self._state.list_mode = not self._state.list_mode

    def _open_packet(self, kind: str) -> None:
        source = self._default_source()
        if source is None:
            self._state.set_toast("No device available", "warning")
            return
        title = "Send packet" if kind == "send_packet" else "Traceroute"
        self._state.modal = ModalState.form(
            kind,
            title,
            ("source", "destination ip", "protocol", "ttl", "size", "payload"),
            [
                source,
                self._state.data.get("default_dst", "10.0.2.10"),
                "ICMP",
                "64",
                "64",
                "",
            ],
        )

    def _default_source(self) -> str | None:
        devices = self._state.data.get("devices", ()) or ()
        for device in devices:
            if device.device_type == "SERVER":
                return device.hostname
        return devices[0].hostname if devices else None

    def _show_history(self) -> None:
        self._state.data["history"] = self._services.simulation.history()
        self._state.data["packet_mode"] = "history"
        self._state.set_toast("Loaded simulation history", "info")

    def _clear_result(self) -> None:
        self._state.data.pop("sim_result", None)
        self._state.data.pop("traceroute", None)
        self._state.data["packet_mode"] = "trace"
        self._state.last_path = ()
        self._state.set_toast("Trace cleared", "info")

    def _open_flow(self) -> None:
        source = self._default_source()
        if source is None:
            self._state.set_toast("No device available", "warning")
            return
        self._state.modal = ModalState.form(
            "flow_new",
            "Start simulated flow",
            ("source", "destination ip", "protocol", "size", "pps", "duration s"),
            [
                source,
                self._state.data.get("default_dst", "10.0.2.10"),
                "TCP",
                "512",
                "5000",
                "60",
            ],
        )

    def _stop_flow(self) -> None:
        flows = self._state.data.get("flows", ()) or ()
        if not flows:
            self._state.set_toast("No active flow", "warning")
            return
        flow = flows[self._state.cursor("traffic_flows", len(flows))]
        self._services.monitoring.stop_flow(flow.flow_id)
        self._load_traffic()
        self._state.set_toast(f"Flow {flow.flow_id} stopped", "warning")

    def _save_settings(self) -> None:
        values = self._state.data.get("settings_values", {}) or {}
        request = SettingsUpdateRequest(
            default_ttl=int(values.get("default_ttl", 64)),
            default_link_capacity=int(values.get("default_link_capacity", 1000)),
            arp_timeout_s=int(values.get("arp_timeout_s", 300)),
            mac_timeout_s=int(values.get("mac_timeout_s", 300)),
            max_hops=int(values.get("max_hops", 64)),
            event_retention=int(values.get("event_retention", 1000)),
            seed=int(values.get("seed", 42)),
            poll_interval_ms=int(values.get("poll_interval_ms", 500)),
        )
        settings = self._services.settings.update(request)
        self._watcher.set_interval(settings.poll_interval_ms / 1000)
        self._load_settings()
        self._state.set_toast("Settings saved", "success")

    def _confirm(self, kind: str, title: str, body: str, submit: str) -> None:
        self._state.modal = ModalState(
            kind=kind,
            title=title,
            body=body,
            submit=submit,
        )

    def _open_help(self) -> None:
        state = self._state
        self._state.modal = ModalState(
            kind="help",
            title=f"Keys — {VIEWS[state.active].title}",
            body=(
                "1-9,0 screens · d SQLite Inspector · tab focus · ctrl+b sidebar\n"
                "↑↓ navigate · ←→ actions · ↵ run · / filter · space pause · "
                "r refresh\n"
                "q quit · esc back · ? help\n\n"
                "All traffic, latency and utilization values are simulated."
            ),
        )

    # ---------------------------------------------------------------- enter
    def _content_enter(self) -> bool:
        state = self._state
        if state.active == "events":
            events = state.data.get("events", ()) or ()
            if not events:
                return False
            event = events[state.cursor("events", len(events))]
            state.modal = ModalState(
                kind="detail",
                title=f"Event #{event.event_id} · {event.severity}",
                body=f"{event.timestamp}\n\n{event.message}\n\n{event.payload_json[:1200]}",
            )
            return True
        if state.active == "packet_lab":
            result = state.data.get("sim_result")
            if result is None or not result.hops:
                return False
            hop = result.hops[state.cursor("hops", len(result.hops))]
            state.modal = ModalState(
                kind="detail",
                title=f"Hop {hop.index} · {hop.kind} · {hop.device_name}",
                body=(
                    f"ingress: {hop.ingress or '—'}\negress: {hop.egress or '—'}\n"
                    f"ttl: {hop.ttl_in} -> {hop.ttl_out}\n"
                    f"route: {hop.matched_route or '—'}\n\n{hop.reason}"
                ),
            )
            return True
        if state.active == "db_inspector":
            snapshot = state.snapshot
            page = snapshot.active_table_page if snapshot else None
            if page is None or not page.rows:
                return False
            index = state.cursor("db_rows", len(page.rows))
            row = page.rows[index]
            body = "\n".join(
                f"{column}: {value}"
                for column, value in zip(page.columns, row, strict=False)
            )
            state.modal = ModalState(
                kind="detail",
                title=f"{page.table_name} row {page.offset + index + 1}",
                body=body[:2000],
            )
            return True
        if state.active == "settings":
            index = state.cursor("settings", len(SETTINGS_FIELDS))
            field = SETTINGS_FIELDS[index]
            values = state.data.get("settings_values", {}) or {}
            state.modal = ModalState.form(
                "settings_edit",
                f"Edit {field}",
                (field,),
                [values.get(field, "")],
            )
            state.data["settings_field"] = field
            return True
        if state.active == "switch_ports":
            self._toggle_port()
            return True
        if state.active == "topology":
            self._toggle_link()
            return True
        return False

    # ---------------------------------------------------------------- submit
    def _submit_modal(self) -> None:
        state = self._state
        modal_state = state.modal
        if modal_state is None:
            return
        try:
            handler = getattr(self, f"_submit_{modal_state.kind}", None)
            if handler is None:
                state.modal = None
                return
            handler(modal_state)
        except ApplicationError as exc:
            modal_state.error = exc.message
        except Exception as exc:
            error = as_application_error(exc)
            modal_state.error = error.message

    def _close_and_toast(self, message: str, severity: str = "success") -> None:
        self._state.modal = None
        self._state.set_toast(message, severity)
        self._load_view(self._state.active)
        self._watcher.refresh_now()

    def _submit_help(self, modal_state: ModalState) -> None:
        self._state.modal = None

    _submit_detail = _submit_help

    def _submit_device_new(self, modal_state: ModalState) -> None:
        values = modal_state.values
        request = CreateDeviceRequest(
            hostname=values[0],
            device_type=values[1].upper(),
            interface_count=int(values[2]),
            location=values[3],
            description=values[4],
        )
        device = self._services.device.create_device(request)
        self._close_and_toast(f"Device {device.hostname} created")

    def _submit_device_edit(self, modal_state: ModalState) -> None:
        device = self._selected_device()
        if device is None:
            return
        request = UpdateDeviceRequest(
            device_id=device.device_id,
            hostname=modal_state.values[0],
            location=modal_state.values[1],
            description=modal_state.values[2],
        )
        self._services.device.update_device(request)
        self._close_and_toast(f"Device {request.hostname} updated")

    def _submit_subnet_new(self, modal_state: ModalState) -> None:
        subnet = self._services.ipam.create_subnet(
            SubnetRequest(
                cidr=modal_state.values[0],
                name=modal_state.values[1],
                gateway=modal_state.values[2],
            )
        )
        self._close_and_toast(f"Subnet {subnet.cidr} created")

    def _submit_assign_ip(self, modal_state: ModalState) -> None:
        hostname, interface, address = modal_state.values
        device = next(
            (
                item
                for item in self._services.device.list_devices()
                if item.hostname == hostname
            ),
            None,
        )
        if device is None:
            raise ApplicationError("APP404", f"Device {hostname} not found.")
        self._services.ipam.assign_address(
            AssignAddressRequest(
                device_id=device.device_id,
                interface_name=interface,
                address=address,
            )
        )
        self._close_and_toast(f"{address} assigned to {hostname} {interface}")

    def _submit_route_new(self, modal_state: ModalState) -> None:
        router = self._selected_router()
        if router is None:
            return
        values = modal_state.values
        self._services.routing.add_static_route(
            RouteRequest(
                router_id=router.device_id,
                destination=values[0],
                next_hop=values[1],
                interface=values[2],
                metric=int(values[3]),
            )
        )
        self._close_and_toast(f"Route added to {router.hostname}")

    def _submit_lpm_lookup(self, modal_state: ModalState) -> None:
        router = self._selected_router()
        if router is None:
            return
        self._state.data["lookup"] = self._services.routing.lookup(
            router.device_id, modal_state.values[0]
        )
        self._state.modal = None

    def _submit_link_new(self, modal_state: ModalState) -> None:
        values = modal_state.values
        self._services.topology.connect(
            ConnectRequest(
                device_a=values[0],
                interface_a=values[1],
                device_b=values[2],
                interface_b=values[3],
                capacity_mbps=int(values[4]),
            )
        )
        self._close_and_toast("Link created")

    def _submit_port_edit(self, modal_state: ModalState) -> None:
        switch = self._selected_switch()
        ports = self._state.data.get("ports", ()) or ()
        if switch is None or not ports:
            return
        port = ports[self._state.cursor("ports", len(ports))]
        self._services.switch.update_port(
            switch.device_id,
            port.number,
            speed_mbps=int(modal_state.values[0]),
            description=modal_state.values[1],
        )
        self._close_and_toast(f"Port {port.number} updated")

    def _resolve_device(self, hostname: str) -> DeviceDTO | None:
        return next(
            (
                item
                for item in self._services.device.list_devices()
                if item.hostname == hostname
            ),
            None,
        )

    def _submit_send_packet(self, modal_state: ModalState) -> None:
        values = modal_state.values
        device = self._resolve_device(values[0])
        if device is None:
            raise ApplicationError("APP404", f"Device {values[0]} not found.")
        result = self._services.simulation.send_packet(
            SendPacketRequest(
                src_device_id=device.device_id,
                dst_ip=values[1],
                protocol=values[2].upper(),
                ttl=int(values[3]),
                size_bytes=int(values[4]),
                payload=values[5],
            )
        )
        self._state.data["sim_result"] = result
        self._state.data["packet_mode"] = "trace"
        self._state.cursors["hops"] = 0
        self._state.last_path = result.path_ids
        self._state.data["last_result_ids"] = result.path_ids
        self._state.modal = None
        self._state.set_toast(
            f"{result.status} · {len(result.hops)} hops",
            "success" if result.status == "DELIVERED" else "error",
            f"{result.total_latency_ms:.2f} ms (sim) · "
            f"{result.drop_reason or 'delivered'}",
        )
        self._watcher.refresh_now()

    def _submit_traceroute(self, modal_state: ModalState) -> None:
        values = modal_state.values
        device = self._resolve_device(values[0])
        if device is None:
            raise ApplicationError("APP404", f"Device {values[0]} not found.")
        result = self._services.simulation.traceroute(
            SendPacketRequest(
                src_device_id=device.device_id,
                dst_ip=values[1],
                protocol=values[2].upper(),
                ttl=int(values[3]),
                size_bytes=int(values[4]),
                payload=values[5],
            )
        )
        self._state.data["traceroute"] = result
        self._state.data["packet_mode"] = "traceroute"
        self._state.modal = None
        self._state.set_toast(
            "Traceroute done" if result.delivered else "Traceroute incomplete",
            "success" if result.delivered else "warning",
            f"{len(result.hops)} probes",
        )
        self._watcher.refresh_now()

    def _submit_flow_new(self, modal_state: ModalState) -> None:
        values = modal_state.values
        device = self._resolve_device(values[0])
        if device is None:
            raise ApplicationError("APP404", f"Device {values[0]} not found.")
        flow = self._services.monitoring.start_flow(
            FlowRequest(
                src_device_id=device.device_id,
                dst_ip=values[1],
                protocol=values[2].upper(),
                packet_size=int(values[3]),
                packets_per_second=int(values[4]),
                duration_s=int(values[5]),
            )
        )
        self._state.modal = None
        self._state.set_toast(
            f"Flow {flow.flow_id} started",
            "success",
            f"{flow.load_mbps:.1f} Mbps (sim)",
        )
        self._load_traffic()
        self._watcher.refresh_now()

    def _submit_export_table(self, modal_state: ModalState) -> None:
        result = self._services.analytics.export_table(
            self._state.inspector_table,
            modal_state.values[0],
            search=self._state.search,
        )
        self._close_and_toast(f"Exported {result.rows} rows to {result.path}")

    def _submit_export_events(self, modal_state: ModalState) -> None:
        filter_request = EventFilterDTO(
            severity=self._state.data.get("event_severity"),
            category=self._state.data.get("event_category"),
            search=self._state.search,
        )
        fmt = "json" if modal_state.values[0].lower().endswith(".json") else "csv"
        result = self._services.event_log.export(
            filter_request, fmt, modal_state.values[0]
        )
        self._close_and_toast(f"Exported {result.rows} events to {result.path}")

    def _submit_settings_edit(self, modal_state: ModalState) -> None:
        field = self._state.data.get("settings_field")
        if field:
            self._state.data["settings_values"][field] = modal_state.values[0]
        self._state.modal = None
        self._state.set_toast(f"{field} updated — press Save", "info")

    def _submit_confirm_delete_device(self, modal_state: ModalState) -> None:
        device = self._selected_device()
        if device is None:
            return
        report = self._services.device.delete_device(device.device_id)
        self._close_and_toast(
            f"Deleted {report.device_name} ({report.links} links removed)", "warning"
        )

    def _submit_confirm_reset_lab(self, modal_state: ModalState) -> None:
        self._services.settings.reset_lab()
        self._state.last_path = ()
        self._close_and_toast("Lab reset", "warning")

    def _submit_confirm_reset_counters(self, modal_state: ModalState) -> None:
        self._services.monitoring.reset_counters()
        self._close_and_toast("Traffic counters reset", "warning")

    def _error(self, exc: Exception) -> None:
        error = as_application_error(exc)
        self._state.set_toast(error.message, "error", error.code)


def render_to_text(app: RichLiveApp, width: int = 120, height: int = 36) -> str:
    """Headless render hook used by tests."""
    app.prepare()
    console = Console(
        width=width,
        height=height,
        record=True,
        force_terminal=False,
        theme=OPENCODE_THEME,
    )
    console.print(app.render(width, height))
    return console.export_text()


__all__ = ["RichLiveApp", "render_to_text"]
