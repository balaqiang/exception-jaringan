"""Real-time data_version watcher thread."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from netcore.application.dto import RealtimeMonitorSnapshotDTO
from netcore.application.ports import AnalyticsQueryPort

logger = logging.getLogger("netcore.analytics.watcher")


class RealtimeDbWatcher:
    """Poll ``PRAGMA data_version`` and push snapshots to the UI queue."""

    def __init__(
        self,
        port: AnalyticsQueryPort,
        *,
        interval_s: float = 0.5,
    ) -> None:
        self._port = port
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._last_version = -1
        self._force = True
        self._table: str | None = None
        self._search = ""
        self._offset = 0
        self._limit = 50
        self._sort_by: str | None = None
        self._descending = True

    def set_interval(self, interval_s: float) -> None:
        """Change the poll interval."""
        self._interval_s = max(0.1, interval_s)

    def set_query(
        self,
        table: str | None,
        *,
        search: str = "",
        sort_by: str | None = None,
        descending: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> None:
        """Set the table page requested inside snapshots."""
        with self._lock:
            self._table = table
            self._search = search
            self._sort_by = sort_by
            self._descending = descending
            self._offset = offset
            self._limit = limit
        self.refresh_now()

    def start(self, on_snapshot: Callable[[RealtimeMonitorSnapshotDTO], None]) -> None:
        """Start the daemon poller."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._force = True
        self._thread = threading.Thread(
            target=self._run,
            args=(on_snapshot,),
            name="netcore-db-watcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop and join the poller."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def pause(self) -> None:
        """Pause automatic polling."""
        self._paused.set()

    def resume(self) -> None:
        """Resume automatic polling."""
        self._paused.clear()
        self.refresh_now()

    def toggle(self) -> bool:
        """Toggle pause state and return True when paused."""
        if self._paused.is_set():
            self.resume()
            return False
        self.pause()
        return True

    @property
    def paused(self) -> bool:
        """Return True when polling is paused."""
        return self._paused.is_set()

    def wake(self) -> None:
        """Wake the poller immediately (EventBus signal)."""
        self._wake.set()

    def refresh_now(self) -> None:
        """Force one snapshot on the next loop iteration."""
        self._force = True
        self._wake.set()

    def _run(self, on_snapshot: Callable[[RealtimeMonitorSnapshotDTO], None]) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=self._interval_s)
            self._wake.clear()
            if self._stop.is_set():
                break
            force = self._force
            self._force = False
            if self._paused.is_set() and not force:
                continue
            try:
                version = self._port.get_data_version()
            except Exception:
                logger.exception("data_version read failed")
                continue
            if not force and version == self._last_version:
                continue
            with self._lock:
                table = self._table
                search = self._search
                offset = self._offset
                limit = self._limit
                sort_by = self._sort_by
                descending = self._descending
            try:
                snapshot = self._port.compute_monitor_snapshot(
                    active_table=table,
                    table_search=search,
                    table_sort_by=sort_by,
                    table_descending=descending,
                    table_offset=offset,
                    table_limit=limit,
                )
            except Exception:
                logger.exception("snapshot computation failed")
                continue
            self._last_version = version
            try:
                on_snapshot(snapshot)
            except Exception:
                logger.exception("snapshot delivery failed")
