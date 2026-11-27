"""Application use cases against real SQLite."""

from __future__ import annotations

from netcore.application.dto import (
    AssignAddressRequest,
    CreateDeviceRequest,
    EventFilterDTO,
    FlowRequest,
    RouteRequest,
    SendPacketRequest,
)


def test_device_ipam_and_routing(container) -> None:
    services = container.services
    device = services.device.create_device(
        CreateDeviceRequest(
            hostname="srv-new",
            device_type="SERVER",
            interface_count=1,
            location="lab",
            description="integration",
        )
    )
    assert device.hostname == "srv-new"
    assert any(item.hostname == "srv-new" for item in services.device.list_devices())
    assert services.device.cycle_status(device.device_id).status == "OFFLINE"

    assigned = services.ipam.assign_address(
        AssignAddressRequest(
            device_id=device.device_id,
            interface_name="eth0",
            address="10.0.1.20/24",
        )
    )
    assert assigned.ip == "10.0.1.20"
    subnet = next(
        item for item in services.ipam.list_subnets() if item.cidr == "10.0.1.0/24"
    )
    assert subnet.used_hosts == 3

    router = next(item for item in services.routing.routers() if item.hostname == "r1")
    route = services.routing.add_static_route(
        RouteRequest(
            router_id=router.device_id,
            destination="10.99.0.0/24",
            next_hop="10.0.12.2",
            interface="ge0/0",
            metric=5,
        )
    )
    assert route.destination == "10.99.0.0/24"
    lookup = services.routing.lookup(router.device_id, "10.99.0.5")
    assert lookup.found
    assert lookup.prefix_len == 24
    services.routing.remove_route(router.device_id, route.route_id)
    assert not services.routing.lookup(router.device_id, "10.99.0.5").found


def test_switch_and_topology(container) -> None:
    services = container.services
    switch = next(
        item for item in services.switch.switches() if item.hostname == "sw-a"
    )
    ports = services.switch.ports(switch.device_id)
    assert len(ports) == 24
    toggled = services.switch.set_port_admin(switch.device_id, 3, False)
    assert not toggled.admin_up
    services.switch.update_port(
        switch.device_id, 3, speed_mbps=10000, description="uplink"
    )
    updated = services.switch.ports(switch.device_id)[2]
    assert updated.speed_mbps == 10000
    assert updated.description == "uplink"
    services.switch.clear_mac_table(switch.device_id)

    links = services.topology.links()
    assert len(links) == 5
    down = services.topology.set_link_admin(links[0].link_id, False)
    assert not down.admin_up
    services.topology.set_link_admin(links[0].link_id, True)
    snapshot = services.topology.snapshot()
    assert len(snapshot.nodes) == 6
    assert len(snapshot.links) == 5


def test_simulation_and_history(container) -> None:
    services = container.services
    source = next(
        item for item in services.device.list_devices() if item.hostname == "srv-a"
    )
    result = services.simulation.send_packet(
        SendPacketRequest(
            src_device_id=source.device_id,
            dst_ip="10.0.2.10",
            protocol="ICMP",
            ttl=64,
            size_bytes=64,
            payload="hello",
        )
    )
    assert result.status == "DELIVERED"
    assert result.run_id > 0
    assert result.path_names[-1] == "srv-b"
    history = services.simulation.history()
    assert history
    assert history[0].run_id == result.run_id
    trace = services.simulation.traceroute(
        SendPacketRequest(
            src_device_id=source.device_id,
            dst_ip="10.0.2.10",
            protocol="ICMP",
            ttl=1,
            size_bytes=64,
        )
    )
    assert trace.delivered


def test_monitoring_flow(container) -> None:
    services = container.services
    source = next(
        item for item in services.device.list_devices() if item.hostname == "srv-a"
    )
    flow = services.monitoring.start_flow(
        FlowRequest(
            src_device_id=source.device_id,
            dst_ip="10.0.2.10",
            protocol="TCP",
            packet_size=9000,
            packets_per_second=10_000,
            duration_s=30,
        )
    )
    assert flow.status == "ACTIVE"
    stats = services.monitoring.link_stats()
    assert any(link.load_mbps > 0 for link in stats)
    dashboard = services.monitoring.dashboard_summary()
    assert dashboard.device_counts["total"] == 6
    services.monitoring.stop_flow(flow.flow_id)
    assert services.monitoring.flows() == ()
    services.monitoring.reset_counters()


def test_event_export(container, tmp_path) -> None:
    services = container.services
    source = next(
        item for item in services.device.list_devices() if item.hostname == "srv-a"
    )
    services.simulation.send_packet(
        SendPacketRequest(
            src_device_id=source.device_id,
            dst_ip="10.0.2.10",
            protocol="ICMP",
            ttl=64,
            size_bytes=64,
        )
    )
    events = services.event_log.query(EventFilterDTO(limit=50))
    assert events
    csv_result = services.event_log.export(
        EventFilterDTO(limit=50), "csv", str(tmp_path / "events")
    )
    assert csv_result.rows == len(events)
    assert (tmp_path / "events.csv").exists()
    json_result = services.event_log.export(
        EventFilterDTO(limit=50), "json", str(tmp_path / "events.json")
    )
    assert json_result.rows == len(events)


def test_settings_and_sample_labs(container) -> None:
    services = container.services
    settings = services.settings.get()
    assert settings.default_ttl == 64
    services.settings.load_sample_lab("spine-leaf")
    devices = services.device.list_devices()
    assert len(devices) == 14
    assert any(item.hostname == "spine-1" for item in devices)
    services.settings.load_sample_lab("two-router")
    assert len(services.device.list_devices()) == 6
