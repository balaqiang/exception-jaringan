"""Immutable application DTOs consumed by the TUI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DeviceDTO:
    device_id: int
    hostname: str
    device_type: str
    status: str
    interface_count: int
    location: str = ""
    description: str = ""
    gateway: str | None = None
    port_count: int | None = None


@dataclass(frozen=True, slots=True)
class InterfaceDTO:
    device_id: int
    device_name: str
    name: str
    mac: str
    ip: str | None
    prefix_len: int | None
    admin_up: bool
    peer: str | None
    port_number: int | None = None
    speed_mbps: int = 1000
    description: str = ""


@dataclass(frozen=True, slots=True)
class DeviceDetailDTO:
    device: DeviceDTO
    interfaces: tuple[InterfaceDTO, ...]


@dataclass(frozen=True, slots=True)
class LinkDTO:
    link_id: int
    endpoint_a: str
    endpoint_b: str
    capacity_mbps: int
    latency_ms: float
    admin_up: bool


@dataclass(frozen=True, slots=True)
class SubnetDTO:
    subnet_id: int
    cidr: str
    name: str
    gateway: str | None
    total_hosts: int
    used_hosts: int
    free_hosts: int
    utilization_pct: float


@dataclass(frozen=True, slots=True)
class RouteDTO:
    route_id: int
    destination: str
    next_hop: str | None
    interface: str
    route_type: str
    admin_distance: int
    metric: int


@dataclass(frozen=True, slots=True)
class RouteLookupDTO:
    found: bool
    message: str
    destination: str | None = None
    next_hop: str | None = None
    interface: str | None = None
    prefix_len: int | None = None


@dataclass(frozen=True, slots=True)
class SwitchPortDTO:
    switch_id: int
    number: int
    admin_up: bool
    speed_mbps: int
    description: str
    peer: str | None
    mac_count: int


@dataclass(frozen=True, slots=True)
class MacEntryDTO:
    mac: str
    port: int
    age_s: float


@dataclass(frozen=True, slots=True)
class TopologyNodeDTO:
    device_id: int
    hostname: str
    device_type: str
    status: str
    interface_count: int


@dataclass(frozen=True, slots=True)
class TopologyLinkDTO:
    link_id: int
    endpoint_a: str
    endpoint_b: str
    admin_up: bool
    capacity_mbps: int


@dataclass(frozen=True, slots=True)
class TopologyDTO:
    name: str
    nodes: tuple[TopologyNodeDTO, ...]
    links: tuple[TopologyLinkDTO, ...]
    subnet_count: int
    path: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class HopDTO:
    index: int
    device_id: int
    device_name: str
    device_type: str
    kind: str
    ingress: str | None
    egress: str | None
    ttl_in: int | None
    ttl_out: int | None
    matched_route: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationResultDTO:
    run_id: int
    status: str
    drop_reason: str | None
    hops: tuple[HopDTO, ...]
    path_names: tuple[str, ...]
    path_ids: tuple[int, ...]
    total_latency_ms: float
    ttl_in: int
    ttl_out: int
    seed: int
    started_at: str


@dataclass(frozen=True, slots=True)
class TracerouteHopDTO:
    ttl: int
    router: str | None
    status: str


@dataclass(frozen=True, slots=True)
class TracerouteDTO:
    hops: tuple[TracerouteHopDTO, ...]
    delivered: bool
    dst_ip: str


@dataclass(frozen=True, slots=True)
class SimulationSummaryDTO:
    run_id: int
    started_at: str
    src_name: str
    dst_ip: str
    status: str
    drop_reason: str | None
    total_latency_ms: float


@dataclass(frozen=True, slots=True)
class EventDTO:
    event_id: int | None
    timestamp: str
    severity: str
    category: str
    device_id: int | None
    device_name: str | None
    message: str
    payload_json: str


@dataclass(frozen=True, slots=True)
class LinkStatsDTO:
    link_id: int
    label: str
    capacity_mbps: int
    load_mbps: float
    utilization_pct: float
    tx_packets: int
    rx_packets: int
    dropped_packets: int
    sparkline: str
    admin_up: bool


@dataclass(frozen=True, slots=True)
class DeviceStatsDTO:
    device_id: int
    hostname: str
    device_type: str
    tx_packets: int
    rx_packets: int
    dropped_packets: int
    top_drop_reason: str | None


@dataclass(frozen=True, slots=True)
class DashboardDTO:
    device_counts: dict[str, int]
    link_counts: dict[str, int]
    subnet_count: int
    events_1h: int
    warnings: int
    errors: int
    top_links: tuple[LinkStatsDTO, ...]
    recent_events: tuple[EventDTO, ...]


@dataclass(frozen=True, slots=True)
class FlowDTO:
    flow_id: int
    src_hostname: str
    dst_ip: str
    protocol: str
    packet_size: int
    packets_per_second: int
    duration_s: int
    remaining_s: int
    load_mbps: float
    utilization_pct: float
    status: str


@dataclass(frozen=True, slots=True)
class RemovalReportDTO:
    device_name: str
    links: int
    routes: int
    interfaces: int


@dataclass(frozen=True, slots=True)
class SettingsDTO:
    default_ttl: int
    default_link_capacity: int
    arp_timeout_s: int
    mac_timeout_s: int
    max_hops: int
    event_retention: int
    seed: int
    poll_interval_ms: int
    db_path: str


@dataclass(frozen=True, slots=True)
class ExportResultDTO:
    path: str
    fmt: str
    rows: int


# ---------------------------------------------------------------- requests
@dataclass(frozen=True, slots=True)
class CreateDeviceRequest:
    hostname: str
    device_type: str
    interface_count: int = 4
    location: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class UpdateDeviceRequest:
    device_id: int
    hostname: str
    location: str
    description: str


@dataclass(frozen=True, slots=True)
class ConnectRequest:
    device_a: str
    interface_a: str
    device_b: str
    interface_b: str
    capacity_mbps: int = 1000


@dataclass(frozen=True, slots=True)
class SendPacketRequest:
    src_device_id: int
    dst_ip: str
    protocol: str = "ICMP"
    ttl: int = 64
    size_bytes: int = 64
    payload: str = ""


@dataclass(frozen=True, slots=True)
class FlowRequest:
    src_device_id: int
    dst_ip: str
    protocol: str = "TCP"
    packet_size: int = 512
    packets_per_second: int = 100
    duration_s: int = 30


@dataclass(frozen=True, slots=True)
class SubnetRequest:
    cidr: str
    name: str = ""
    gateway: str = ""


@dataclass(frozen=True, slots=True)
class AssignAddressRequest:
    device_id: int
    interface_name: str
    address: str


@dataclass(frozen=True, slots=True)
class RouteRequest:
    router_id: int
    destination: str
    next_hop: str
    interface: str
    metric: int = 0


@dataclass(frozen=True, slots=True)
class EventFilterDTO:
    severity: str | None = None
    category: str | None = None
    device_id: int | None = None
    search: str = ""
    limit: int = 200


@dataclass(frozen=True, slots=True)
class SettingsUpdateRequest:
    default_ttl: int
    default_link_capacity: int
    arp_timeout_s: int
    mac_timeout_s: int
    max_hops: int
    event_retention: int
    seed: int
    poll_interval_ms: int


# --------------------------------------------------------------- analytics
@dataclass(frozen=True, slots=True)
class DbTableMetaDTO:
    name: str
    row_count: int
    column_names: tuple[str, ...]
    last_updated_at: str | None


@dataclass(frozen=True, slots=True)
class ColumnStatsDTO:
    column: str
    dtype: str
    non_null_count: int
    null_count: int
    unique_count: int
    min_val: str | None
    max_val: str | None
    mean_val: float | None
    p50_val: float | None
    p95_val: float | None


@dataclass(frozen=True, slots=True)
class TablePageDTO:
    table_name: str
    total_rows: int
    filtered_rows: int
    offset: int
    limit: int
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    column_stats: tuple[ColumnStatsDTO, ...]
    query_ms: float


@dataclass(frozen=True, slots=True)
class LatencyMetricsDTO:
    sample_count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    sparkline: str


@dataclass(frozen=True, slots=True)
class LinkAnalyticsDTO:
    link_id: int
    label: str
    capacity_mbps: int
    load_mbps: float
    utilization_pct: float
    ema_utilization_pct: float
    tx_packets: int
    rx_packets: int
    dropped_packets: int
    sparkline: str
    is_anomaly: bool
    admin_up: bool


@dataclass(frozen=True, slots=True)
class DbHealthDTO:
    db_path: str
    journal_mode: str
    file_size_kb: float
    wal_size_kb: float
    data_version: int
    total_tables: int
    total_rows: int
    last_poll_ms: float
    polled_at_utc: str


@dataclass(frozen=True, slots=True)
class RealtimeMonitorSnapshotDTO:
    db_health: DbHealthDTO
    tables: tuple[DbTableMetaDTO, ...]
    device_counts: dict[str, int] = field(default_factory=dict)
    link_counts: dict[str, int] = field(default_factory=dict)
    subnet_utilization_pct: float = 0.0
    latency: LatencyMetricsDTO | None = None
    link_analytics: tuple[LinkAnalyticsDTO, ...] = ()
    recent_events: tuple[EventDTO, ...] = ()
    active_table_page: TablePageDTO | None = None
