"""Parameterised SQL repositories and row/domain mappers."""

from __future__ import annotations

import ipaddress
import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from netcore.domain.addressing import MacAddress
from netcore.domain.arp import ArpEntry
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router, RoutingEntry
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import MacTableEntry, Switch
from netcore.domain.enums import (
    DeviceStatus,
    DeviceType,
    EntryType,
    EventCategory,
    RouteType,
    Severity,
)
from netcore.domain.events import NetworkEvent
from netcore.domain.interface import NetworkInterface
from netcore.domain.link import InterfaceRef, Link
from netcore.domain.simulation.result import SimulationResult
from netcore.domain.subnet import Subnet
from netcore.domain.topology import NetworkTopology


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _iso(value: datetime) -> str:
    return value.isoformat()


def _interface_key(device_id: int, index: int) -> int:
    return device_id * 1000 + index


class SqliteTopologyRepository:
    """Load and save the whole topology aggregate."""

    def __init__(
        self, conn: sqlite3.Connection, *, now: datetime | None = None
    ) -> None:
        self._conn = conn
        self._now = now or datetime.now(UTC)

    # ------------------------------------------------------------------ load
    def load(self) -> NetworkTopology:
        """Rebuild the aggregate from persisted rows."""
        topology = NetworkTopology("lab")
        subnet_rows = self._conn.execute("SELECT * FROM subnets ORDER BY id").fetchall()
        for row in subnet_rows:
            topology.add_subnet(
                Subnet(
                    id=int(row["id"]),
                    network=ipaddress.IPv4Network(row["cidr"]),
                    name=row["name"],
                    gateway=(
                        ipaddress.IPv4Address(row["gateway"])
                        if row["gateway"]
                        else None
                    ),
                    parent_id=row["parent_id"],
                )
            )
        device_rows = self._conn.execute("SELECT * FROM devices ORDER BY id").fetchall()
        for row in device_rows:
            device = self._make_device(row)
            topology.add_device(device)
        interface_map: dict[int, InterfaceRef] = {}
        iface_rows = self._conn.execute(
            "SELECT * FROM interfaces ORDER BY device_id, name"
        ).fetchall()
        for row in iface_rows:
            device = topology.get_device(row["device_id"])
            interface = NetworkInterface(
                name=row["name"],
                mac=MacAddress(row["mac"]),
                address=(
                    ipaddress.IPv4Interface(f"{row['ip_address']}/{row['prefix_len']}")
                    if row["ip_address"]
                    else None
                ),
                admin_up=bool(row["admin_up"]),
                port_number=row["port_number"],
                speed_mbps=row["speed_mbps"],
                description=row["description"],
            )
            device.add_interface(interface)
            interface_map[row["id"]] = InterfaceRef(row["device_id"], row["name"])
        for row in self._conn.execute("SELECT * FROM links ORDER BY id"):
            a = interface_map.get(row["interface_a_id"])
            b = interface_map.get(row["interface_b_id"])
            if a is None or b is None:
                continue
            link = topology.connect(
                a,
                b,
                capacity_mbps=row["capacity_mbps"],
                latency_ms=row["latency_ms"],
                link_id=int(row["id"]),
            )
            link.admin_up = bool(row["admin_up"])
        for row in self._conn.execute("SELECT * FROM routes ORDER BY device_id, id"):
            device = topology.get_device(row["device_id"])
            if not isinstance(device, Router):
                continue
            destination = ipaddress.IPv4Network(row["destination"])
            route_type = RouteType(row["route_type"])
            device.routing_table.add(
                RoutingEntry(
                    id=row["id"],
                    destination=destination,
                    next_hop=(
                        ipaddress.IPv4Address(row["next_hop"])
                        if row["next_hop"]
                        else None
                    ),
                    interface=row["interface_name"],
                    route_type=route_type,
                    admin_distance=row["admin_distance"],
                    metric=row["metric"],
                    insertion_index=len(device.routing_table.entries()),
                )
            )
        for device in topology.routers():
            device.sync_connected()
        for row in self._conn.execute("SELECT * FROM arp_entries ORDER BY id"):
            device = topology.get_device(row["device_id"])
            table = getattr(device, "arp_table", None)
            if table is None:
                continue
            entry = ArpEntry(
                ip=ipaddress.IPv4Address(row["ip"]),
                mac=MacAddress(row["mac"]),
                interface=row["interface_name"],
                learned_at=self._now,
                expires_at=_dt(row["expires_at"]),
                entry_type=EntryType(row["entry_type"]),
            )
            table._entries[str(entry.ip)] = entry
        for row in self._conn.execute("SELECT * FROM mac_entries ORDER BY id"):
            device = topology.get_device(row["device_id"])
            if not isinstance(device, Switch):
                continue
            entry = MacTableEntry(
                mac=row["mac"],
                port=row["port_number"],
                learned_at=self._now,
                expires_at=_dt(row["expires_at"]) or self._now,
            )
            device.mac_table._entries[entry.mac] = entry
        topology.seed_counters(
            device=len(device_rows) + 1,
            link=len(topology.links()) + 1,
            subnet=len(subnet_rows) + 1,
            route=self._max_id("routes") + 1,
        )
        return topology

    def _make_device(self, row: sqlite3.Row) -> NetworkDevice:
        device_type = DeviceType(row["device_type"])
        device_id = int(row["id"])
        location = str(row["location"])
        description = str(row["description"])
        if device_type is DeviceType.ROUTER:
            device = Router(
                row["hostname"],
                device_id=device_id,
                location=location,
                description=description,
                interfaces=[],
            )
        elif device_type is DeviceType.SWITCH:
            device = Switch(
                row["hostname"],
                device_id=device_id,
                port_count=row["port_count"] or 24,
                location=location,
                description=description,
                interfaces=[],
            )
        else:
            device = Server(
                row["hostname"],
                device_id=device_id,
                location=location,
                description=description,
                interfaces=[],
                default_gateway=(
                    ipaddress.IPv4Address(row["default_gateway"])
                    if row["default_gateway"]
                    else None
                ),
            )
        device.set_status(DeviceStatus(row["status"]))
        return device

    def _max_id(self, table: str) -> int:
        row = self._conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}").fetchone()
        return int(row[0])

    # ------------------------------------------------------------------ save
    def save(self, topology: NetworkTopology) -> None:
        """Upsert every aggregate member inside the current transaction."""
        now = _iso(self._now)
        subnet_ids = {subnet.id for subnet in topology.subnets()}
        device_ids = {device.id for device in topology.devices()}
        # Links, routes, interfaces, ARP and MAC rows are cheap derived state.
        # Replacing them avoids UNIQUE collisions while changing labs.
        self._conn.execute("DELETE FROM links")
        self._conn.execute("DELETE FROM routes")
        self._conn.execute("DELETE FROM interfaces")
        self._conn.execute("DELETE FROM arp_entries")
        self._conn.execute("DELETE FROM mac_entries")
        self._delete_missing("devices", device_ids)
        self._delete_missing("subnets", subnet_ids)
        for subnet in topology.subnets():
            self._conn.execute(
                """
                INSERT INTO subnets(id, cidr, name, gateway, parent_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    cidr=excluded.cidr, name=excluded.name,
                    gateway=excluded.gateway, parent_id=excluded.parent_id
                """,
                (
                    subnet.id,
                    str(subnet.network),
                    subnet.name,
                    str(subnet.gateway) if subnet.gateway else None,
                    subnet.parent_id,
                ),
            )
        for device in topology.devices():
            gateway = (
                str(device.default_gateway)
                if isinstance(device, Server) and device.default_gateway
                else None
            )
            port_count = device.port_count if isinstance(device, Switch) else None
            self._conn.execute(
                """
                INSERT INTO devices(
                    id, hostname, device_type, status, location, description,
                    default_gateway, port_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    hostname=excluded.hostname, device_type=excluded.device_type,
                    status=excluded.status, location=excluded.location,
                    description=excluded.description,
                    default_gateway=excluded.default_gateway,
                    port_count=excluded.port_count, updated_at=excluded.updated_at
                """,
                (
                    device.id,
                    device.hostname,
                    device.device_type.value,
                    device.status.value,
                    device.location,
                    device.description,
                    gateway,
                    port_count,
                    now,
                    now,
                ),
            )
        self._delete_missing("devices", device_ids)

        interface_ids: dict[tuple[int, str], int] = {}
        for device in topology.devices():
            for index, interface in enumerate(device.interfaces(), start=1):
                interface_id = _interface_key(device.id, index)
                interface_ids[(device.id, interface.name)] = interface_id
                subnet = (
                    topology.subnet_for(interface.address.ip)
                    if interface.address is not None
                    else None
                )
                self._conn.execute(
                    """
                    INSERT INTO interfaces(
                        id, device_id, name, mac, ip_address, prefix_len, subnet_id,
                        admin_up, port_number, speed_mbps, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        device_id=excluded.device_id, name=excluded.name,
                        mac=excluded.mac, ip_address=excluded.ip_address,
                        prefix_len=excluded.prefix_len, subnet_id=excluded.subnet_id,
                        admin_up=excluded.admin_up, port_number=excluded.port_number,
                        speed_mbps=excluded.speed_mbps, description=excluded.description
                    """,
                    (
                        interface_id,
                        device.id,
                        interface.name,
                        interface.mac.value,
                        str(interface.address.ip) if interface.address else None,
                        interface.address.network.prefixlen
                        if interface.address
                        else None,
                        subnet.id if subnet else None,
                        int(interface.admin_up),
                        interface.port_number,
                        interface.speed_mbps,
                        interface.description,
                    ),
                )
        for link in topology.links():
            a = interface_ids.get((link.endpoint_a.device_id, link.endpoint_a.name))
            b = interface_ids.get((link.endpoint_b.device_id, link.endpoint_b.name))
            if a is None or b is None:
                continue
            self._conn.execute(
                """
                INSERT INTO links(
                    id, interface_a_id, interface_b_id, capacity_mbps,
                    latency_ms, admin_up
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    interface_a_id=excluded.interface_a_id,
                    interface_b_id=excluded.interface_b_id,
                    capacity_mbps=excluded.capacity_mbps,
                    latency_ms=excluded.latency_ms, admin_up=excluded.admin_up
                """,
                (
                    link.id,
                    a,
                    b,
                    link.capacity_mbps,
                    link.latency_ms,
                    int(link.admin_up),
                ),
            )
        for router in topology.routers():
            for route in router.routing_table.entries():
                if route.route_type is RouteType.CONNECTED:
                    continue
                if route.id <= 0:
                    continue
                self._conn.execute(
                    """
                    INSERT INTO routes(
                        id, device_id, destination, next_hop, interface_name,
                        route_type, admin_distance, metric
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        device_id=excluded.device_id,
                        destination=excluded.destination,
                        next_hop=excluded.next_hop,
                        interface_name=excluded.interface_name,
                        route_type=excluded.route_type,
                        admin_distance=excluded.admin_distance,
                        metric=excluded.metric
                    """,
                    (
                        route.id,
                        router.id,
                        str(route.destination),
                        str(route.next_hop) if route.next_hop else None,
                        route.interface,
                        route.route_type.value,
                        route.admin_distance,
                        route.metric,
                    ),
                )

        self._conn.execute("DELETE FROM arp_entries")
        for device in topology.devices():
            table = getattr(device, "arp_table", None)
            if table is None:
                continue
            for entry in table.entries(self._now):
                self._conn.execute(
                    """
                    INSERT INTO arp_entries(
                        device_id, ip, mac, interface_name, entry_type, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device.id,
                        str(entry.ip),
                        entry.mac.value,
                        entry.interface,
                        entry.entry_type.value,
                        _iso(entry.expires_at) if entry.expires_at else None,
                    ),
                )
        self._conn.execute("DELETE FROM mac_entries")
        for device in topology.switches():
            for entry in device.mac_table.entries(self._now):
                self._conn.execute(
                    """
                    INSERT INTO mac_entries(
                        device_id, mac, port_number, expires_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (device.id, entry.mac, entry.port, _iso(entry.expires_at)),
                )

    def _delete_missing(self, table: str, keep: set[int]) -> None:
        if not keep:
            self._conn.execute(f"DELETE FROM {table}")
            return
        placeholders = ",".join("?" for _ in keep)
        self._conn.execute(
            f"DELETE FROM {table} WHERE id NOT IN ({placeholders})",
            tuple(keep),
        )


class SqliteEventRepository:
    """Audit event persistence."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, event: NetworkEvent) -> int:
        """Insert one event and return its id."""
        cursor = self._conn.execute(
            """
            INSERT INTO events(
                timestamp, severity, category, device_id, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _iso(event.timestamp),
                event.severity.value,
                event.category.value,
                event.device_id,
                event.message,
                json.dumps(event.payload, default=str),
            ),
        )
        return int(cursor.lastrowid or 0)

    def query(
        self,
        *,
        severity: str | None = None,
        category: str | None = None,
        device_id: int | None = None,
        search: str = "",
        limit: int = 200,
        offset: int = 0,
    ) -> list[NetworkEvent]:
        """Query events newest first with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if device_id is not None:
            clauses.append("device_id = ?")
            params.append(device_id)
        if search:
            clauses.append("(message LIKE ? OR payload_json LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        rows = self._conn.execute(
            f"""
            SELECT * FROM events {where}
            ORDER BY id DESC LIMIT ? OFFSET ?
            """,
            tuple(params),
        ).fetchall()
        return [self._to_event(row) for row in rows]

    def prune(self, keep: int) -> int:
        """Keep only the newest ``keep`` events."""
        cursor = self._conn.execute(
            """
            DELETE FROM events WHERE id NOT IN (
                SELECT id FROM events ORDER BY id DESC LIMIT ?
            )
            """,
            (keep,),
        )
        return int(cursor.rowcount or 0)

    def counts_since(self, since: datetime) -> dict[str, int]:
        """Count warnings and errors since a timestamp."""
        rows = self._conn.execute(
            """
            SELECT severity, COUNT(*) AS total FROM events
            WHERE timestamp >= ? GROUP BY severity
            """,
            (_iso(since),),
        ).fetchall()
        return {row["severity"]: int(row["total"]) for row in rows}

    def _to_event(self, row: sqlite3.Row) -> NetworkEvent:
        return NetworkEvent(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            severity=Severity(row["severity"]),
            category=EventCategory(row["category"]),
            device_id=row["device_id"],
            message=row["message"],
            payload=json.loads(row["payload_json"] or "{}"),
        )


class SqliteSimulationRepository:
    """Simulation run, hop and traffic-counter persistence."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, result: SimulationResult) -> int:
        """Persist a run and its hops, returning the run id."""
        cursor = self._conn.execute(
            """
            INSERT INTO simulation_runs(
                started_at, src_device_id, dst_ip, protocol, ttl, size_bytes,
                status, drop_reason, total_latency_ms, seed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _iso(result.started_at),
                result.src_device_id,
                result.dst_ip,
                result.protocol.value,
                result.ttl,
                result.size_bytes,
                result.status.value,
                result.drop_reason.value if result.drop_reason else None,
                result.total_latency_ms,
                result.seed,
            ),
        )
        run_id = int(cursor.lastrowid or 0)
        for hop in result.hops:
            self._conn.execute(
                """
                INSERT INTO hop_records(
                    run_id, hop_index, device_id, kind, ingress, egress,
                    ttl_in, ttl_out, matched_route, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    hop.index,
                    hop.device_id,
                    hop.kind.value,
                    hop.ingress,
                    hop.egress,
                    hop.ttl_in,
                    hop.ttl_out,
                    hop.matched_route,
                    hop.reason,
                ),
            )
        return run_id

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent runs newest first."""
        rows = self._conn.execute(
            """
            SELECT r.*, d.hostname AS src_name
            FROM simulation_runs r
            LEFT JOIN devices d ON d.id = r.src_device_id
            ORDER BY r.id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def hops(self, run_id: int) -> list[dict[str, Any]]:
        """Return hops for one run."""
        rows = self._conn.execute(
            "SELECT * FROM hop_records WHERE run_id = ? ORDER BY hop_index",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def replace_counters(
        self, rows: list[tuple[int | None, int | None, str, int, int, int]]
    ) -> None:
        """Replace all simulated traffic counters."""
        self._conn.execute("DELETE FROM traffic_counters")
        self._conn.executemany(
            """
            INSERT INTO traffic_counters(
                device_id, link_id, direction, packets, bytes, dropped
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


class SqliteSettingsRepository:
    """Key/value settings persistence."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_all(self) -> dict[str, str]:
        """Return every setting."""
        return {
            row["key"]: row["value"]
            for row in self._conn.execute("SELECT key, value FROM settings")
        }

    def update(self, values: dict[str, str]) -> None:
        """Upsert multiple settings."""
        self._conn.executemany(
            """
            INSERT INTO settings(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            tuple(values.items()),
        )


__all__ = [
    "Link",
    "SqliteEventRepository",
    "SqliteSettingsRepository",
    "SqliteSimulationRepository",
    "SqliteTopologyRepository",
]
