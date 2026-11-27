"""SQLite connection factory (WAL, foreign keys, busy timeout)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a read-write connection with the required pragmas."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def open_read_only(db_path: str | Path) -> sqlite3.Connection:
    """Open a read-only URI connection for the analytics poller."""
    path = Path(db_path)
    conn = sqlite3.connect(
        f"file:{path}?mode=ro",
        uri=True,
        timeout=2.0,
        check_same_thread=True,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    conn.execute("PRAGMA busy_timeout = 2000;")
    return conn
