"""View registry."""

from netcore.tui.views.base import BaseView, ViewContent
from netcore.tui.views.dashboard import DashboardView
from netcore.tui.views.db_inspector import DbInspectorView
from netcore.tui.views.devices import DevicesView
from netcore.tui.views.event_logs import EventLogsView
from netcore.tui.views.ipam import IpamView
from netcore.tui.views.packet_lab import PacketLabView
from netcore.tui.views.routing import RoutingView
from netcore.tui.views.settings import SettingsView
from netcore.tui.views.switch_ports import SwitchPortsView
from netcore.tui.views.topology import TopologyView
from netcore.tui.views.traffic_monitor import TrafficMonitorView

VIEWS: dict[str, BaseView] = {
    view.id: view
    for view in (
        DashboardView(),
        TopologyView(),
        PacketLabView(),
        TrafficMonitorView(),
        DevicesView(),
        IpamView(),
        RoutingView(),
        SwitchPortsView(),
        DbInspectorView(),
        EventLogsView(),
        SettingsView(),
    )
}

__all__ = ["VIEWS", "BaseView", "ViewContent"]
