"""Forward-only SQL migration runner."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

DEFAULT_SETTINGS: dict[str, str] = {
    "default_ttl": "64",
    "default_link_capacity": "1000",
    "arp_timeout_s": "300",
    "mac_timeout_s": "300",
    "max_hops": "64",
    "event_retention": "1000",
    "seed": "42",
    "poll_interval_ms": "500",
}


class Migrator:
    """Apply every not-yet-applied ``NNNN_name.sql`` file."""

    def __init__(self, conn: sqlite3.Connection, directory: Path | None = None) -> None:
        self._conn = conn
        self._directory = directory or MIGRATIONS_DIR

    def migrate(self) -> list[int]:
        """Apply pending migrations and return their versions."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied = {
            row[0]
            for row in self._conn.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        versions: list[int] = []
        for path in sorted(self._directory.glob("*.sql")):
            version = int(path.name.split("_", 1)[0])
            if version in applied:
                continue
            self._conn.executescript(path.read_text(encoding="utf-8"))
            self._conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            self._conn.commit()
            versions.append(version)
        self._seed_settings()
        return versions

    def _seed_settings(self) -> None:
        for key, value in DEFAULT_SETTINGS.items():
            self._conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )
        self._conn.commit()
