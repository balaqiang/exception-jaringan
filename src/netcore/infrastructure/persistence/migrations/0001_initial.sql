PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subnets (
    id INTEGER PRIMARY KEY,
    cidr TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    gateway TEXT,
    parent_id INTEGER REFERENCES subnets(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL COLLATE NOCASE UNIQUE,
    device_type TEXT NOT NULL CHECK (device_type IN ('ROUTER', 'SWITCH', 'SERVER')),
    status TEXT NOT NULL DEFAULT 'ONLINE'
        CHECK (status IN ('ONLINE', 'OFFLINE', 'MAINTENANCE')),
    location TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    default_gateway TEXT,
    port_count INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interfaces (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    mac TEXT NOT NULL UNIQUE,
    ip_address TEXT UNIQUE,
    prefix_len INTEGER,
    subnet_id INTEGER REFERENCES subnets(id) ON DELETE SET NULL,
    admin_up INTEGER NOT NULL DEFAULT 1,
    port_number INTEGER,
    speed_mbps INTEGER NOT NULL DEFAULT 1000,
    description TEXT NOT NULL DEFAULT '',
    UNIQUE (device_id, name)
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    interface_a_id INTEGER NOT NULL UNIQUE REFERENCES interfaces(id) ON DELETE CASCADE,
    interface_b_id INTEGER NOT NULL UNIQUE REFERENCES interfaces(id) ON DELETE CASCADE,
    capacity_mbps INTEGER NOT NULL CHECK (capacity_mbps BETWEEN 1 AND 400000),
    latency_ms REAL NOT NULL DEFAULT 0.1,
    admin_up INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    destination TEXT NOT NULL,
    next_hop TEXT,
    interface_name TEXT NOT NULL,
    route_type TEXT NOT NULL CHECK (route_type IN ('CONNECTED', 'STATIC', 'DEFAULT')),
    admin_distance INTEGER NOT NULL DEFAULT 1,
    metric INTEGER NOT NULL DEFAULT 0,
    UNIQUE (device_id, destination, next_hop, interface_name)
);

CREATE TABLE IF NOT EXISTS arp_entries (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    ip TEXT NOT NULL,
    mac TEXT NOT NULL,
    interface_name TEXT NOT NULL,
    entry_type TEXT NOT NULL DEFAULT 'DYNAMIC',
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS mac_entries (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    mac TEXT NOT NULL,
    port_number INTEGER NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    src_device_id INTEGER NOT NULL,
    dst_ip TEXT NOT NULL,
    protocol TEXT NOT NULL,
    ttl INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL,
    drop_reason TEXT,
    total_latency_ms REAL NOT NULL,
    seed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS hop_records (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    hop_index INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    ingress TEXT,
    egress TEXT,
    ttl_in INTEGER,
    ttl_out INTEGER,
    matched_route TEXT,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traffic_counters (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    link_id INTEGER REFERENCES links(id) ON DELETE CASCADE,
    direction TEXT NOT NULL,
    packets INTEGER NOT NULL DEFAULT 0,
    bytes INTEGER NOT NULL DEFAULT 0,
    dropped INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
CREATE INDEX IF NOT EXISTS idx_hop_records_run ON hop_records(run_id);
CREATE INDEX IF NOT EXISTS idx_interfaces_device ON interfaces(device_id);
CREATE INDEX IF NOT EXISTS idx_traffic_link ON traffic_counters(link_id);
