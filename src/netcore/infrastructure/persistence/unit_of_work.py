"""SQLite unit of work with explicit transaction boundaries."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from netcore.infrastructure.persistence.connection import open_connection
from netcore.infrastructure.persistence.repositories import (
    SqliteEventRepository,
    SqliteSettingsRepository,
    SqliteSimulationRepository,
    SqliteTopologyRepository,
)


class SqliteUnitOfWork:
    """One connection, one transaction, typed repositories."""

    def __init__(self, db_path: str | Path, *, now: datetime | None = None) -> None:
        self._db_path = db_path
        self._now = now or datetime.now(UTC)
        self._conn: sqlite3.Connection | None = None
        self._committed = False
        self.topology: SqliteTopologyRepository
        self.events: SqliteEventRepository
        self.simulations: SqliteSimulationRepository
        self.settings: SqliteSettingsRepository

    def __enter__(self) -> SqliteUnitOfWork:
        self._conn = open_connection(self._db_path)
        self._conn.execute("BEGIN")
        self._committed = False
        self.topology = SqliteTopologyRepository(self._conn, now=self._now)
        self.events = SqliteEventRepository(self._conn)
        self.simulations = SqliteSimulationRepository(self._conn)
        self.settings = SqliteSettingsRepository(self._conn)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._conn is not None
        try:
            if exc_type is None and self._committed:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the active connection."""
        assert self._conn is not None
        return self._conn

    def commit(self) -> None:
        """Mark the transaction for commit on clean exit."""
        assert self._conn is not None
        self._conn.commit()
        self._committed = True

    def rollback(self) -> None:
        """Roll the transaction back immediately."""
        assert self._conn is not None
        self._conn.rollback()
        self._committed = False
