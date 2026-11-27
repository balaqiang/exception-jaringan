"""AT-11 SQLite persistence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from netcore.application.labs import build_two_router_lab
from netcore.domain.devices.router import Router
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.events import NetworkEvent
from netcore.infrastructure.clock import FixedClock
from netcore.infrastructure.persistence.connection import open_connection
from netcore.infrastructure.persistence.migrator import Migrator
from netcore.infrastructure.persistence.unit_of_work import SqliteUnitOfWork


@pytest.fixture
def db_path(tmp_path) -> str:
    path = str(tmp_path / "persist.db")
    conn = open_connection(path)
    try:
        Migrator(conn).migrate()
    finally:
        conn.close()
    return path


def test_round_trip_reference_lab(db_path: str) -> None:
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    topology = build_two_router_lab()
    with SqliteUnitOfWork(db_path, now=clock.now()) as uow:
        uow.topology.save(topology)
        uow.commit()
    with SqliteUnitOfWork(db_path, now=clock.now()) as uow:
        loaded = uow.topology.load()
    assert [device.hostname for device in loaded.devices()] == [
        "srv-a",
        "sw-a",
        "r1",
        "r2",
        "sw-b",
        "srv-b",
    ]
    assert len(loaded.links()) == 5
    assert len(loaded.subnets()) == 3
    srv_a = loaded.require_device("srv-a")
    assert str(srv_a.get_interface("eth0").address) == "10.0.1.10/24"
    r1 = loaded.require_device("r1")
    assert isinstance(r1, Router)
    static = [
        entry
        for entry in r1.routing_table.entries()
        if entry.destination.compressed == "10.0.2.0/24"
    ]
    assert len(static) == 1
    assert str(static[0].next_hop) == "10.0.12.2"
    assert static[0].id > 0


def test_ids_survive_delete_and_reload(db_path: str) -> None:
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    topology = build_two_router_lab()
    with SqliteUnitOfWork(db_path, now=clock.now()) as uow:
        uow.topology.save(topology)
        uow.commit()
    with SqliteUnitOfWork(db_path, now=clock.now()) as uow:
        loaded = uow.topology.load()
        r1_id = loaded.require_device("r1").id
        loaded.remove_device(loaded.require_device("sw-b").id)
        uow.topology.save(loaded)
        uow.commit()
    with SqliteUnitOfWork(db_path, now=clock.now()) as uow:
        reloaded = uow.topology.load()
        assert reloaded.require_device("r1").id == r1_id
        assert {link.id for link in reloaded.links()} == {1, 2, 3}
        assert all(
            link.endpoint_a.device_id in reloaded._devices for link in reloaded.links()
        )


def test_migrator_is_idempotent(db_path: str) -> None:
    conn = open_connection(db_path)
    try:
        assert Migrator(conn).migrate() == []
    finally:
        conn.close()


def test_event_query_and_prune(db_path: str) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with SqliteUnitOfWork(db_path, now=now) as uow:
        for index in range(5):
            uow.events.add(
                NetworkEvent(
                    timestamp=now,
                    severity=Severity.INFO if index % 2 else Severity.WARNING,
                    category=EventCategory.SYSTEM,
                    message=f"event {index}",
                )
            )
        uow.commit()
    with SqliteUnitOfWork(db_path, now=now) as uow:
        assert len(uow.events.query(limit=10)) == 5
        assert len(uow.events.query(severity="WARNING", limit=10)) == 3
        assert len(uow.events.query(search="event 4", limit=10)) == 1
        assert uow.events.prune(2) == 3
        assert len(uow.events.query(limit=10)) == 2
        uow.commit()


def _insert_then_fail(uow) -> None:
    uow.events.add(
        NetworkEvent(
            timestamp=datetime.now(UTC),
            severity=Severity.INFO,
            category=EventCategory.SYSTEM,
            message="must roll back",
        )
    )
    raise RuntimeError("boom")


def test_rollback_on_exception(db_path: str) -> None:
    with pytest.raises(RuntimeError), SqliteUnitOfWork(db_path) as uow:
        _insert_then_fail(uow)
    with SqliteUnitOfWork(db_path) as uow:
        assert uow.events.query(limit=10) == []
