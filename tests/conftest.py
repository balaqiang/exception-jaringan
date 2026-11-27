"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from netcore.application.labs import build_two_router_lab
from netcore.bootstrap import AppContainer, build_container
from netcore.domain.topology import NetworkTopology
from netcore.tui.app import RichLiveApp


@pytest.fixture
def two_router_lab() -> NetworkTopology:
    """Reference topology from NETWORK_SPEC §13."""
    return build_two_router_lab()


@pytest.fixture
def container(tmp_path) -> Iterator[AppContainer]:
    """Seeded application container on a temp SQLite file."""
    built = build_container(str(tmp_path / "netcore.db"), seed_lab="two-router")
    yield built
    built.reader.close()


@pytest.fixture
def empty_container(tmp_path) -> Iterator[AppContainer]:
    """Empty application container."""
    built = build_container(str(tmp_path / "empty.db"), seed_lab=None)
    yield built
    built.reader.close()


@pytest.fixture
def app(container: AppContainer) -> RichLiveApp:
    """Prepared headless Rich app."""
    app = RichLiveApp(container.services, container.watcher, container.reader)
    app.prepare()
    return app
