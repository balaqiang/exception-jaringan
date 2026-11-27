"""AT-12 keyboard navigation and headless Rich rendering."""

from __future__ import annotations

import pytest

from netcore.bootstrap import build_container
from netcore.tui.app import RichLiveApp, render_to_text
from netcore.tui.input_handler import KeyEvent
from netcore.tui.state import FocusZone

VIEW_KEYS = [
    ("1", "dashboard", "Dashboard"),
    ("2", "devices", "Devices"),
    ("3", "ipam", "IPAM Subnets"),
    ("4", "routing", "Routing Table"),
    ("5", "switch_ports", "Switch Ports"),
    ("6", "topology", "Topology"),
    ("7", "packet_lab", "Packet Lab"),
    ("8", "traffic", "Traffic Monitor"),
    ("9", "events", "Event Logs"),
    ("0", "settings", "Settings"),
    ("d", "db_inspector", "SQLite Inspector"),
]


def press(app: RichLiveApp, kind: str, char: str = "") -> None:
    app.handle_key(KeyEvent(kind, char))


def run_action(app: RichLiveApp, action_id: str) -> None:
    app.state.focus = FocusZone.ACTIONS
    actions = app._actions()
    app.state.action_index = [action.id for action in actions].index(action_id)
    press(app, "ENTER")


@pytest.mark.parametrize(("key", "view_id", "title"), VIEW_KEYS)
def test_every_screen_renders(
    app: RichLiveApp, key: str, view_id: str, title: str
) -> None:
    press(app, "CHAR", key)
    assert app.active_view == view_id
    text = render_to_text(app)
    assert title in text
    assert "Terminal too small" not in text
    assert "nan" not in text.lower()


def test_at12_full_keyboard_navigation(app: RichLiveApp) -> None:
    for key, view_id, _title in VIEW_KEYS:
        press(app, "CHAR", key)
        assert app.active_view == view_id
    press(app, "TAB")
    assert app.state.focus is FocusZone.ACTIONS
    press(app, "TAB")
    assert app.state.focus is FocusZone.CONTENT
    press(app, "TAB")
    assert app.state.focus is FocusZone.SIDEBAR


def test_responsive_guards(app: RichLiveApp) -> None:
    small = render_to_text(app, 80, 24)
    assert "Terminal too small" in small
    collapsed = render_to_text(app, 100, 30)
    assert "OPERATIONS" not in collapsed
    assert "Dashboard" in collapsed
    full = render_to_text(app, 120, 36)
    assert "OPERATIONS" in full
    assert "CONFIGURATION" in full
    assert "DATABASE & LOGS" in full


def test_sidebar_toggle_at_narrow_width(app: RichLiveApp) -> None:
    assert "OPERATIONS" not in render_to_text(app, 100, 30)
    press(app, "CTRL_B")
    assert "OPERATIONS" in render_to_text(app, 100, 30)


def test_header_telemetry_and_toast(app: RichLiveApp) -> None:
    text = render_to_text(app)
    assert "db WAL" in text
    assert "devices 6" in text
    app.state.set_toast("test toast", "warning")
    assert "test toast" in render_to_text(app)


def test_pause_toggle(app: RichLiveApp) -> None:
    press(app, "CHAR", " ")
    assert app.state.paused
    assert "paused" in render_to_text(app)
    press(app, "CHAR", " ")
    assert not app.state.paused


def test_packet_lab_end_to_end(app: RichLiveApp) -> None:
    press(app, "CHAR", "7")
    run_action(app, "send_packet")
    modal = app.state.modal
    assert modal is not None
    assert modal.kind == "send_packet"
    modal.values[:] = ["srv-a", "10.0.2.10", "ICMP", "64", "64", "test"]
    press(app, "ENTER")
    assert app.state.modal is None
    result = app.state.data["sim_result"]
    assert result.status == "DELIVERED"
    assert result.path_names[-1] == "srv-b"
    assert app.state.last_path
    text = render_to_text(app)
    assert "DELIVERED" in text
    assert "srv-b" in text


def test_packet_modal_cancel(app: RichLiveApp) -> None:
    press(app, "CHAR", "7")
    run_action(app, "send_packet")
    assert app.state.modal is not None
    press(app, "ESC")
    assert app.state.modal is None


def test_db_inspector_switch_filter_and_stats(app: RichLiveApp) -> None:
    press(app, "CHAR", "d")
    app.prime_snapshot()
    page = app.state.snapshot.active_table_page
    assert page is not None
    assert page.table_name == "devices"
    run_action(app, "switch_table")
    app.prime_snapshot()
    assert app.state.inspector_table == "interfaces"
    assert app.state.snapshot.active_table_page.table_name == "interfaces"
    press(app, "CHAR", "/")
    for char in "eth0":
        press(app, "CHAR", char)
    app.prime_snapshot()
    assert app.state.snapshot.active_table_page.filtered_rows == 2
    press(app, "ENTER")
    assert not app.state.filter_active
    run_action(app, "col_stats")
    assert app.state.modal is not None
    assert "Pandas" in app.state.modal.title
    press(app, "ESC")


def test_content_navigation_and_enter(app: RichLiveApp) -> None:
    press(app, "CHAR", "2")
    app.state.focus = FocusZone.CONTENT
    press(app, "DOWN")
    assert app.state.cursors.get("devices", 0) == 1
    press(app, "UP")
    assert app.state.cursors.get("devices", 0) == 0
    press(app, "CHAR", "9")
    app.state.focus = FocusZone.CONTENT
    press(app, "ENTER")
    assert app.state.modal is not None
    press(app, "ESC")


def test_empty_database_renders_cleanly(tmp_path) -> None:
    container = build_container(str(tmp_path / "empty.db"), seed_lab=None)
    app = RichLiveApp(container.services, container.watcher, container.reader)
    try:
        text = render_to_text(app)
        assert "No links" in text or "No devices" in text
        assert "nan" not in text.lower()
        assert "None" not in text
    finally:
        container.reader.close()
