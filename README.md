# NetCore TUI

Data Center Network Management & Traffic Simulator — a keyboard-first
terminal application built with **Rich**, **pandas**, **NumPy** and
stdlib **SQLite**.

Everything is simulated: no socket, subprocess or host network change is
performed by `src/`. Traffic, latency and utilization values are computed
from the model and always labelled as simulated.

## Features

- Routers, switches and servers with validated IPv4/MAC addressing.
- IPAM subnets, gateway and next-free-address assignment.
- Connected, static and default routes with integer longest-prefix match.
- Switch ports, administrative state and MAC address learning.
- Layered topology canvas with link up/down toggles and path highlight.
- Deterministic packet simulation with ARP, TTL decrement per router hop,
  drop reasons, traceroute and explained hop traces.
- Simulated traffic flows, capacity vs utilization, and NumPy p50/p95/p99
  latency plus Unicode sparklines.
- Live SQLite Inspector: 13-table browser, Pandas column statistics,
  filtering, pagination and CSV/JSON export.
- Audit event log with severity/category filters and live tail.
- Sample labs: `two-router` (reference topology) and `spine-leaf`
  (2 spines, 4 leaves, 8 servers).

## Requirements

- Python 3.12+
- `rich`, `pandas`, `numpy` (runtime)
- `pytest`, `ruff`, `ty` (development)

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
python -m netcore
python -m netcore --db ./lab.db --seed spine-leaf
python -m netcore --render --width 120 --height 36   # one headless frame
```

The default database is `$XDG_STATE_HOME/netcore/netcore.db`
(`~/.local/state/netcore/netcore.db`). `NETCORE_DB` overrides it.
When the database is empty, `--seed two-router` (default) or
`--seed spine-leaf` loads a sample lab; `--seed none` starts empty.

Minimum terminal size is **100×30**. At 80×24 the application shows a
guard instead of the layout.

## Keyboard

| Key | Action |
| --- | --- |
| `1`–`9`, `0` | Dashboard, Devices, IPAM, Routing, Switch Ports, Topology, Packet Lab, Traffic, Events, Settings |
| `d` / `D` | SQLite Inspector |
| `Tab` / `Shift+Tab` | Cycle focus: sidebar → actions → content |
| `↑` `↓` | Navigate sidebar, actions or table rows |
| `←` `→` | Move between action buttons / switch inspector table / port grid |
| `Enter` | Run focused action or open row detail |
| `/` | Inline filter (SQLite Inspector, Events, Devices) |
| `Space` | Pause / resume real-time polling |
| `r` | Force SQLite re-poll and view refresh |
| `Ctrl+B` | Toggle sidebar |
| `?` | Key help |
| `Esc` | Back / close modal / clear filter |
| `q` / `Ctrl+C` | Quit |

## Screens

| Screen | Purpose |
| --- | --- |
| Dashboard | Device/link counts, IPAM utilization, simulated latency, events |
| Topology | Router/switch/server canvas, link administration, path highlight |
| Packet Lab | Send packet or traceroute, hop-by-hop decision trace |
| Traffic Monitor | Link load, utilization bars, sparklines, active flows |
| Devices | CRUD, status cycle, interface inspector |
| IPAM Subnets | Subnet capacity, assign/release IPv4 addresses |
| Routing Table | Router selector, route CRUD, interactive LPM lookup |
| Switch Ports | 12-per-row port grid, admin toggle, MAC table |
| SQLite Inspector | Live 13-table browser, Pandas stats, filter, export |
| Event Logs | Filterable audit trail, live tail, CSV/JSON export |
| Settings | TTL, ARP/MAC timeout, max hops, retention, seed, poll rate, labs |

## Architecture

Layered modular monolith:

```text
netcore.tui            Rich views, components, raw keyboard loop
      ↓
netcore.application    services, ports, EventBus, frozen DTOs
      ↓
netcore.domain         pure stdlib network model and simulation engine
      ↑
netcore.infrastructure SQLite persistence, pandas/NumPy analytics, watcher
```

- `netcore.domain` imports no Rich/pandas/numpy/sqlite3 and performs no I/O.
- `netcore.application` returns frozen DTOs only.
- `netcore.tui` never imports sqlite3, pandas, numpy or infrastructure.
- SQL lives only in parameterised repositories.
- `src/netcore/bootstrap.py` is the single composition root.

The real-time monitor is a daemon thread with its own read-only WAL
connection. It polls `PRAGMA data_version`, wakes immediately on
in-process EventBus signals, computes a snapshot and posts it to the UI
queue. Only the main thread mutates state and calls `rich.live.Live`.

## Network behaviour

- IPv4 parsing rejects leading zeros, spaces, host bits in subnets and
  reserved network/broadcast addresses.
- LPM is implemented on `ipaddress` networks, never strings; ties break
  by admin distance, metric, then insertion order.
- Routers decrement TTL and drop with `TTL_EXPIRED` at zero.
- Switches forward on destination MAC only and learn source MACs.
- ARP is explicit per device, does not consume TTL and is visible in the
  hop trace.
- Offline devices, admin-down links/interfaces and down switch ports
  produce typed drop reasons.
- Capacity is configuration; utilization is derived from active simulated
  flows and never persisted as configuration.

Full rules: `docs/NETWORK_SPEC.md`.

## Tests and quality gates

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
ty check src/netcore
```

The suite covers AT-01…AT-12 (delivery, validation, duplicates, LPM, TTL,
offline, link down, invalid port, persistence, keyboard navigation),
NumPy empty/NaN safety, WAL concurrent writes, and layer import guards.

## Project layout

```text
docs/            product, architecture, network, UI and UML specs
.ai/             agent roles, skills and project state
src/netcore/     application package
tests/           architecture, unit, integration and TUI tests
```

## Legacy assignment

This repository originated as the P9 OOP assignment
“Simulasi Jaringan Komputer — Exception Handling”. The original flat
files remain in `src/exceptions.py`, `src/models.py`, `src/main.py` and
`src/test_models.py` for reference, but the NetCore package is now the
maintained implementation and preserves the original class names
(`NetworkDevice`, `Router`, `Switch`, `Server`, `Packet`, `Link`,
`NetworkTopology`, `LoggerMixin`).

## Team (original assignment)

| NIM | Name | GitHub |
| --- | --- | --- |
| 2501020053 | I Putu Bala Krishna Dasa | balaqiang |
| 2501020052 | I Putu Gede Swanjaya | PetengSz |
| 2501020062 | Dimas Raditya Putu Jati | dimasradityaputujati |

Licensed under the Apache License 2.0. Simulation only.
