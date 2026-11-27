# NETCORE — TASK BOARD

Owned by ORCHESTRATOR. Agents update only the `Status` and `Notes` of
tasks assigned to them; the ORCHESTRATOR adds, splits and re-prioritises.

## Conventions

- **ID:** `T-<phase><nn>` (e.g., `T-101` = phase 1, task 01).
- **Status:** `TODO` · `READY` (deps done) · `IN_PROGRESS` · `REVIEW` ·
  `BLOCKED` · `DONE` (verified, reviewed, state updated).
- **Owner:** one agent role. Reviewer is always `CODE_REVIEWER`.
- **Size:** S (< 1 h), M (1–3 h), L (> 3 h — should be split).
- A task moves to `DONE` only when every acceptance criterion is checked
  and the required commands were actually run (CLAUDE.md §13).

Status legend for criteria: `[ ]` open · `[x]` verified.

---

## Phase 0 — Project Scaffolding

### T-001 Create project skeleton and tooling
- Owner: ARCHITECT · Size: S · Status: READY · Deps: —
- Files: `pyproject.toml`, `README.md`, `src/netcore/__init__.py`,
  `src/netcore/__main__.py`, `tests/conftest.py`, `.gitignore`
- Acceptance:
  - [ ] `pyproject.toml` matches ARCHITECTURE.md §6 (textual; dev: pytest, pytest-asyncio, ruff, ty).
  - [ ] Directory tree from ARCHITECTURE.md §2 exists with `__init__.py` files.
  - [ ] `python -m netcore --version` prints version.
  - [ ] All four quality gates run (pytest may report "no tests").
- Skill: `.ai/skills/quality-gates.md`

### T-002 Architecture import-rule tests
- Owner: QA_ENGINEER · Size: S · Status: TODO · Deps: T-001
- Files: `tests/architecture/test_layer_imports.py`
- Acceptance:
  - [ ] Test fails if `netcore.domain` imports textual/sqlite3/application/infrastructure/tui.
  - [ ] Test fails if `netcore.tui` imports sqlite3/infrastructure.
  - [ ] Test fails if `src/` imports `socket`, `subprocess`, or calls `os.system`.
- Skill: `.ai/skills/architecture-guard.md`

---

## Phase 1 — Core Network Engine (domain only)

### T-101 Domain enums and error hierarchy
- Owner: NETWORK_ENGINEER · Size: S · Status: TODO · Deps: T-001
- Files: `domain/enums.py`, `domain/errors.py`
- Acceptance:
  - [ ] All enums from UML.md §4 exist.
  - [ ] Error classes and codes from NETWORK_SPEC §12 / UML §5 exist; each carries `code` and `message`.

### T-102 Addressing value objects and validators
- Owner: NETWORK_ENGINEER · Size: M · Status: TODO · Deps: T-101
- Files: `domain/addressing.py`, `tests/unit/domain/test_addressing.py`
- Acceptance:
  - [ ] IPv4 parsing rules of NETWORK_SPEC §2.1 incl. leading-zero rejection.
  - [ ] `MacAddress` normalisation (`:`, `-`, `.`), rejects broadcast/multicast.
  - [ ] Deterministic MAC generator (seeded, `02:` prefix).
  - [ ] AT-02 test passes.

### T-103 LoggerMixin, NetworkInterface, Subnet, Link
- Owner: NETWORK_ENGINEER · Size: M · Status: TODO · Deps: T-102
- Files: `domain/logging_mixin.py`, `domain/interface.py`, `domain/subnet.py`, `domain/link.py`
- Acceptance:
  - [ ] Signatures match UML §2.
  - [ ] Subnet reserved-address rules incl. /31, /32.
  - [ ] Link rejects same-device endpoints.

### T-104 NetworkDevice, Router, Switch, Server
- Owner: NETWORK_ENGINEER · Size: L→split if needed · Status: TODO · Deps: T-103
- Files: `domain/devices/*.py`
- Acceptance:
  - [ ] Abstract `NetworkDevice` with `receive()` abstract.
  - [ ] Interface count limits (NETWORK_SPEC §3).
  - [ ] Switch ports 1..N, `InvalidPortError` (AT-10).
  - [ ] Private attributes not exposed; read-only properties used.

### T-105 RoutingTable with longest prefix match
- Owner: NETWORK_ENGINEER · Size: M · Status: TODO · Deps: T-104
- Files: `domain/devices/router.py`, `tests/unit/domain/test_routing_table.py`
- Acceptance:
  - [ ] Example table in NETWORK_SPEC §6.2 returns all 5 expected matches (AT-06).
  - [ ] Connected routes sync with interface addresses.
  - [ ] `InvalidNextHopError`, `DuplicateRouteError`.

### T-106 MacTable and ArpTable
- Owner: NETWORK_ENGINEER · Size: M · Status: TODO · Deps: T-104
- Files: `domain/devices/switch.py`, `domain/arp.py`
- Acceptance:
  - [ ] Expiry uses injected `now`.
  - [ ] Static ARP entries never expire.

### T-107 NetworkTopology aggregate
- Owner: NETWORK_ENGINEER · Size: L · Status: TODO · Deps: T-105, T-106
- Files: `domain/topology.py`, `tests/unit/domain/test_topology.py`
- Acceptance:
  - [ ] Duplicate hostname/IP/MAC rejected (AT-03, AT-04).
  - [ ] Overlapping subnets rejected.
  - [ ] `connect` enforces one link per interface.
  - [ ] `is_operational` per NETWORK_SPEC §3.1.
  - [ ] `l2_segment` stops at routers.
  - [ ] `remove_device` returns RemovalReport and cleans links/routes.

### T-108 Packet, Frame, NetworkEvent, TrafficEvent
- Owner: NETWORK_ENGINEER · Size: S · Status: TODO · Deps: T-101
- Files: `domain/packet.py`, `domain/events.py`
- Acceptance:
  - [ ] Frozen dataclasses; `Packet.with_ttl` returns new instance.
  - [ ] TTL range 1..255, size 64..9000 validated.

### T-109 ForwardingEngine (single packet + traceroute)
- Owner: NETWORK_ENGINEER · Size: L · Status: TODO · Deps: T-107, T-108
- Files: `domain/simulation/*.py`, `tests/fixtures/two_router_lab.py`,
  `tests/unit/domain/test_forwarding_engine.py`
- Acceptance:
  - [ ] AT-01 delivered, TTL 64→62, path `srv-a, sw-a, r1, r2, sw-b, srv-b`.
  - [ ] AT-05 NO_ROUTE, AT-07 TTL_EXPIRED, AT-08 DEVICE_OFFLINE, AT-09 LINK_DOWN.
  - [ ] Switch never reads dst IP (assert via test double).
  - [ ] ARP hops visible, do not decrement TTL.
  - [ ] Hop limit guard; deterministic with seed.
  - [ ] Single packet ≤ 50 hops < 50 ms (NFR-01).
- Skill: `.ai/skills/network-scenario-test.md`

### T-110 TrafficGenerator and utilization
- Owner: NETWORK_ENGINEER · Size: M · Status: TODO · Deps: T-109
- Files: `domain/simulation/traffic.py`
- Acceptance:
  - [ ] Formula NETWORK_SPEC §10.2; capacity never mutated.
  - [ ] CONGESTION drops when load > capacity.

### T-111 Phase 1 review
- Owner: CODE_REVIEWER · Size: M · Status: TODO · Deps: T-101..T-110
- Acceptance:
  - [ ] Review report per `.ai/agents/code-reviewer.md`, no blocking findings open.
  - [ ] Domain coverage ≥ 90 %.

---

## Phase 2 — Persistence

### T-201 Schema migration 0001 and Migrator
- Owner: DATABASE_ENGINEER · Size: M · Status: TODO · Deps: T-107
- Files: `infrastructure/persistence/migrations/0001_initial.sql`, `migrator.py`, `connection.py`
- Acceptance:
  - [ ] Tables per UML §10 with FK, UNIQUE, CHECK constraints.
  - [ ] Pragmas: foreign_keys, WAL, busy_timeout.
  - [ ] Migrator idempotent; records `schema_migrations`.

### T-202 Ports and SqliteUnitOfWork
- Owner: DATABASE_ENGINEER (ports reviewed by ARCHITECT) · Size: M · Status: TODO · Deps: T-201
- Files: `application/ports.py`, `infrastructure/persistence/unit_of_work.py`
- Acceptance:
  - [ ] Commit on success, rollback + re-raise on exception.

### T-203 Topology, Event, Simulation, Settings repositories + mappers
- Owner: DATABASE_ENGINEER · Size: L · Status: TODO · Deps: T-202
- Acceptance:
  - [ ] Round-trip test: build reference lab → save → load → equal (AT-11).
  - [ ] Parameterised SQL only.
  - [ ] Event pruning keeps N most recent.

### T-204 Seed labs (two-router, spine-leaf)
- Owner: DATABASE_ENGINEER + NETWORK_ENGINEER · Size: M · Status: TODO · Deps: T-203
- Acceptance:
  - [ ] Spine-leaf: 2 spines, 4 leaves, 8 servers, valid addressing; packet between any two servers is DELIVERED.

---

## Phase 3 — Application Services

### T-301 DTOs, ApplicationError, EventBus
- Owner: ARCHITECT · Size: M · Status: TODO · Deps: T-202
### T-302 Device, IPAM, Routing, Switch, Topology services
- Owner: NETWORK_ENGINEER · Size: L · Status: TODO · Deps: T-301, T-203
### T-303 Simulation, Monitoring, EventLog, Settings services
- Owner: NETWORK_ENGINEER · Size: L · Status: TODO · Deps: T-302
### T-304 bootstrap composition root + CLI args
- Owner: ARCHITECT · Size: S · Status: TODO · Deps: T-303

Acceptance for T-302/T-303:
  - [ ] Each service method has a unit test with fake UoW and one integration test with in-memory SQLite.
  - [ ] No `textual` or `sqlite3` import in `application/`.
  - [ ] Domain errors mapped to ApplicationError with same code.

---

## Phase 4 — TUI

### T-401 App shell, theme, sidebar, global bindings, too-small screen
- Owner: TUI_ENGINEER · Size: M · Status: TODO · Deps: T-304
### T-402 Reusable widgets (UI_SPEC §6)
- Owner: TUI_ENGINEER · Size: L · Status: TODO · Deps: T-401
### T-403 Dashboard, Devices, IPAM screens
- Owner: TUI_ENGINEER · Size: L · Status: TODO · Deps: T-402
### T-404 Routing, Switch Ports, Topology screens
- Owner: TUI_ENGINEER · Size: L · Status: TODO · Deps: T-402
### T-405 Packet Lab, Traffic, Event Logs, Settings screens
- Owner: TUI_ENGINEER · Size: L · Status: TODO · Deps: T-402
### T-406 TUI Pilot tests incl. AT-12
- Owner: QA_ENGINEER · Size: M · Status: TODO · Deps: T-403..T-405

Acceptance for Phase 4:
  - [ ] All screens reachable via `1`–`0`; AT-12 passes.
  - [ ] Long operations in workers; no UI freeze.
  - [ ] All UI_SPEC §9 error/empty states implemented.

---

## Phase 5 — Hardening & Documentation

### T-501 Coverage & performance verification (NFR-01, NFR-02, NFR-06)
- Owner: QA_ENGINEER · Status: TODO
### T-502 User guide in README (install, run, keymap, sample lab walkthrough)
- Owner: TUI_ENGINEER · Status: TODO
### T-503 Final review and release checklist
- Owner: CODE_REVIEWER · Status: TODO

---

## Phase 6 — Delivered Rich/Analytics Baseline

These tasks supersede overlapping earlier T-xxx items for presentation,
analytics and the current implementation baseline. Every criterion was
verified with the commands in `PROJECT_STATE.md`.

### T-TUI-01 Dependencies, ADRs, analytics DTOs and port
- Owner: ARCHITECT · Size: S · Status: DONE
- Files: `pyproject.toml`, `.ai/context/DECISIONS.md`,
  `application/dto.py`, `application/ports.py`
- Acceptance: [x] rich/pandas/numpy added; [x] DEC-016..018 accepted;
  [x] frozen analytics DTOs and `AnalyticsQueryPort` defined.

### T-TUI-02 Read-only SQLite + Pandas/NumPy analytics
- Owner: DATABASE_ENGINEER · Size: L · Status: DONE
- Files: `infrastructure/analytics/**`
- Acceptance: [x] read-only WAL connection; [x] table whitelist;
  [x] data_version watcher; [x] Pandas pages/column stats;
  [x] NumPy percentiles/EMA/sparklines; [x] empty/NaN safe.

### T-TUI-03 AnalyticsService
- Owner: NETWORK_ENGINEER · Size: S · Status: DONE
- Files: `application/services/analytics_service.py`
- Acceptance: [x] no pandas/sqlite leak; [x] snapshot/table/export API.

### T-TUI-04 Theme, state, input, layout
- Owner: TUI_ENGINEER · Size: M · Status: DONE
- Files: `tui/theme.py`, `tui/state.py`, `tui/input_handler.py`,
  `tui/layout.py`
- Acceptance: [x] OpenCode palette; [x] FocusZone machine;
  [x] POSIX/Windows raw keyboard; [x] 100×30 guard and collapse.

### T-TUI-05 Components
- Owner: TUI_ENGINEER · Size: L · Status: DONE
- Files: `tui/components/**`
- Acceptance: [x] 10 borderless components; [x] visible focus;
  [x] no outer box chrome.

### T-TUI-06 Real-time views
- Owner: TUI_ENGINEER · Size: L · Status: DONE
- Files: `views/db_inspector.py`, `views/dashboard.py`,
  `views/traffic_monitor.py`, `views/event_logs.py`
- Acceptance: [x] pause/resume; [x] table switching/filter/stats/export;
  [x] NumPy sparklines; [x] live tail.

### T-TUI-07 Management and simulation views
- Owner: TUI_ENGINEER · Size: L · Status: DONE
- Files: `views/{devices,ipam,routing,switch_ports,topology,packet_lab,settings}.py`
- Acceptance: [x] CRUD modals; [x] packet/traceroute flows;
  [x] port grid and link toggles; [x] sample labs and settings.

### T-TUI-08 Composition root and loop
- Owner: ARCHITECT + TUI_ENGINEER · Size: M · Status: DONE
- Files: `bootstrap.py`, `tui/app.py`, `__main__.py`
- Acceptance: [x] single composition root; [x] dual-trigger watcher;
  [x] graceful shutdown; [x] headless `--render`.

### T-TUI-09 Tests and architecture guards
- Owner: QA_ENGINEER · Size: M · Status: DONE
- Files: `tests/**`
- Acceptance: [x] AT-01..AT-12; [x] WAL external write test;
  [x] empty/NaN tests; [x] import guards; [x] responsive renders.

---

## Parallelisation Map

```
T-001 ─┬─ T-002
       └─ T-101 ─┬─ T-102 ─ T-103 ─ T-104 ─┬─ T-105 ─┐
                 └─ T-108                  └─ T-106 ─┴─ T-107 ─ T-109 ─ T-110 ─ T-111
T-107 ─ T-201 ─ T-202 ─┬─ T-203 ─ T-204
                       └─ T-301 ─ T-302 ─ T-303 ─ T-304 ─ T-401 ─ T-402 ─┬─ T-403 ┐
                                                                         ├─ T-404 ┼─ T-406
                                                                         └─ T-405 ┘
```

Safe parallel pairs (no shared files): T-002 ‖ T-101; T-105 ‖ T-106;
T-108 ‖ T-102..T-104; T-203 ‖ T-301; T-403 ‖ T-404 ‖ T-405.
