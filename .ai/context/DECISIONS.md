# NETCORE — ARCHITECTURE DECISION LOG

Lightweight ADR log. Each decision is immutable once `ACCEPTED`; to
change it, add a new decision that `SUPERSEDES` the old one.

Status values: `PROPOSED` → `ACCEPTED` | `REJECTED`; later `SUPERSEDED`.
Only a human may move a decision to `ACCEPTED` when it touches a gate in
`CLAUDE.md §15`. Agents may record `PROPOSED` entries.

Template:

```
## DEC-NNN: <title>
- Status: PROPOSED | ACCEPTED | REJECTED | SUPERSEDED by DEC-XXX
- Date: YYYY-MM-DD
- Deciders: <human / agent roles>
- Context: why a decision is needed
- Decision: what was chosen
- Alternatives: options considered and why rejected
- Consequences: positive / negative / follow-up tasks
```

---

## DEC-001: Use Python 3.12+ and Textual

- Status: SUPERSEDED (presentation layer) by DEC-016
- Date: 2026-11-27
- Deciders: Human
- Context: The product is a terminal application for education; it must
  be cross-platform and easy to install.
- Decision: Python ≥ 3.12; Textual for the presentation layer.
- Alternatives: curses (too low-level), urwid (smaller ecosystem),
  prompt_toolkit (not screen-oriented), Rich only (no interactivity).
- Consequences: Async-aware UI, CSS-like styling, built-in Pilot test
  harness. Textual must stay confined to `netcore.tui`.

## DEC-002: Use SQLite for local persistence

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: Labs, configuration and event history must survive restarts
  with zero setup.
- Decision: Single SQLite file accessed via stdlib `sqlite3`.
- Alternatives: JSON files (no transactions/queries), PostgreSQL (needs
  a server).
- Consequences: Transactions and foreign keys available; one writer at
  a time — workers use separate connections.

## DEC-003: Preserve the original OOP foundation

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: Project originates from a UTS (mid-term) OOP assignment with
  classes `NetworkDevice`, `Router`, `Switch`, `Server`, `Packet`,
  `Link`, `NetworkTopology`, `LoggerMixin`.
- Decision: Keep these class names, the inheritance
  `NetworkDevice → Router/Switch/Server`, and `LoggerMixin` as a mixin.
  Fix protocol defects inside them rather than replacing them.
- Alternatives: Rewrite with a pure functional engine (loses
  educational OOP value).
- Consequences: New models (`RoutingEntry`, `SwitchPort`,
  `NetworkInterface`, `Subnet`, `TrafficEvent`, `SimulationResult`,
  `NetworkEvent`) are added around the original classes.

## DEC-004: Default to simulation-only mode

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: Safety and scope.
- Decision: No sockets, raw packets, subprocess or host network access
  in `src/`. Enforced by an architecture test.
- Consequences: Any real integration needs a new spec and human
  approval (CLAUDE.md §12, §15).

## DEC-005: Layered Modular Monolith with ports

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human, ARCHITECT
- Context: Several agents work in parallel; boundaries must be explicit.
- Decision: Layers `tui → application → domain`; `infrastructure`
  implements `typing.Protocol` ports declared in `application.ports`.
  Composition root in `netcore/bootstrap.py`. `src/` layout.
- Alternatives: Flat package (coupling), microservices (overkill),
  full hexagonal with separate packages (too heavy).
- Consequences: Import rules tested in `tests/architecture/`.

## DEC-006: No ORM — repositories with hand-written SQL

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: ARCHITECT, DATABASE_ENGINEER
- Context: Schema is small; dependency count should stay low;
  learners benefit from readable SQL.
- Decision: stdlib `sqlite3`, parameterised queries only, mappers in
  `infrastructure/persistence/mappers.py`, forward-only `.sql`
  migrations.
- Alternatives: SQLAlchemy (heavy dependency), Peewee.
- Consequences: Mapper code must be unit-tested; no string-formatted SQL.

## DEC-007: Use `ty` for static type checking (replaces mypy)

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human (project description explicitly specifies ty)
- Context: The earlier `CLAUDE.md` listed `python -m mypy src/netcore`,
  while the human project description specifies **ty** for static
  type checking, Ruff for lint/format and pytest for tests. Explicit
  human requirements take priority (CLAUDE.md §03).
- Decision: Quality gate is `ty check src/netcore`. mypy is not used.
- Alternatives: mypy (slower, conflicting configuration), pyright.
- Consequences: `pyproject.toml` contains `[tool.ty]`; ty is still
  evolving, so a rule that misbehaves may be suppressed with a targeted
  `# ty: ignore[<rule>]` plus a justification comment — never blanket
  ignores.

## DEC-008: NetworkTopology is the aggregate root

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: ARCHITECT, NETWORK_ENGINEER
- Context: Uniqueness of IP/MAC/hostname and link exclusivity span
  multiple devices.
- Decision: All cross-device mutations go through `NetworkTopology`
  methods. Repositories load/save the whole topology (labs are small:
  target ≤ 200 devices).
- Alternatives: Per-device repositories with DB constraints only
  (invariants leak into infrastructure).
- Consequences: DB UNIQUE constraints still exist as a second safety
  net. Revisit if labs exceed NFR-02 size.

## DEC-009: Integer longest prefix match

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: NETWORK_ENGINEER
- Context: Original UTS code used string prefix matching (defect).
- Decision: Use `ipaddress` membership and `prefixlen`; tie-break by AD,
  metric, insertion order (NETWORK_SPEC §6.2). Linear scan is
  acceptable for tables ≤ 1 000 entries.
- Consequences: Radix trie may be introduced later behind the same
  `RoutingTable.longest_prefix_match` interface.

## DEC-010: Explicit simulated ARP

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: NETWORK_ENGINEER, Human (CLAUDE.md §08 requires explicit ARP)
- Context: Switches forward on MAC, so L3→L2 resolution must exist.
- Decision: Per-device `ArpTable`, broadcast request flooded within the
  L2 segment, reply from owner, cache with simulation-time expiry,
  visible as `ARP` hop records that do not consume TTL (NETWORK_SPEC §7).
- Alternatives: Global IP→MAC oracle (hides learning, rejected).
- Consequences: Traces are longer but educational.

## DEC-011: Capacity vs utilization are separate fields

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: NETWORK_ENGINEER
- Context: Original code had no utilization and risked mixing
  bandwidth with usage.
- Decision: `Link.capacity_mbps` is configuration; utilization is
  computed from active simulated flows (NETWORK_SPEC §10) and never
  persisted as configuration. UI labels all traffic numbers "simulated".
- Consequences: No real measurements are ever fabricated.

## DEC-012: Deterministic simulation with injected clock and RNG

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: ARCHITECT, QA_ENGINEER
- Decision: Domain receives `now: datetime` and `random.Random(seed)`;
  application provides them via a `Clock` port and settings seed.
- Consequences: Reproducible tests and replays.

## DEC-013: Synchronous in-process EventBus

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: ARCHITECT
- Context: Dashboard, traffic monitor and event log need live updates.
- Decision: Simple synchronous pub/sub in `application/event_bus.py`.
  Events are persisted first, then published after commit. TUI bridge
  marshals to the Textual thread.
- Alternatives: asyncio queues in the domain (couples domain to
  asyncio), polling only (laggy).
- Consequences: Handlers must be fast and must not raise; handler
  errors are logged and do not break the publisher.

## DEC-014: Testing stack

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: QA_ENGINEER, Human
- Decision: pytest, run in-memory SQLite (`:memory:`) for integration
  tests, and headless Rich `Console(record=True)` rendering for TUI.
  No snapshot-testing dependency without approval.
- Consequences: TUI tests run headless in CI.

## DEC-015: Hierarchical multi-agent orchestration with skills

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: Development uses Spec-Driven Development, Hierarchical
  Multi-Agent Orchestration and Skill-Based Execution.
- Decision: ORCHESTRATOR plans and delegates to six specialist roles
  (`.ai/agents/*.md`); reusable procedures live in `.ai/skills/*.md`;
  shared state lives in `.ai/context/`. File ownership per role is
  defined in `CLAUDE.md §05`.
- Consequences: Every task must pass DISCOVER → … → DOCUMENT and the
  agent output contract.

---

## DEC-016: Replace Textual with Rich + raw keyboard loop

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human (product owner direction, precedence #1)
- Context: The human requires an OpenCode-style flat TUI rendered
  pixel-accurately, without the boxed CSS model of Textual.
- Decision: `rich.console.Live(screen=True, auto_refresh=False)` plus a
  stdlib raw-mode non-blocking keyboard loop (`termios`/`tty`/`select`
  on POSIX, `msvcrt` on Windows). Frames are pushed manually on dirty
  state or tick. Threads + `queue.Queue` replace async workers.
- Alternatives: Textual (rejected: styling model and async coupling),
  curses (too low-level).
- Consequences: DEC-001 presentation clause and DEC-014 pytest-asyncio
  clause are superseded. `rich` is confined to `netcore.tui`.

## DEC-017: pandas and numpy confined to infrastructure analytics

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: The SQLite inspector and traffic monitor need DataFrame
  pagination, aggregation and vectorised percentile/EMA math.
- Decision: `pandas`/`numpy` live only in
  `netcore.infrastructure.analytics`; one export adapter may use pandas
  in `application/services/event_log_service.py`. Domain stays pure
  stdlib; TUI receives frozen DTOs only.
- Alternatives: stdlib-only statistics (slower, more code), putting
  DataFrames in DTOs (leaks infrastructure).
- Consequences: Empty/NaN arrays must be guarded; every UI numeric is
  finite and rounded before DTO construction.

## DEC-018: OpenCode flat dark aesthetic and SQLite Inspector

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: `UI_SPEC.md` v1.0 described boxed Textual panels that do not
  match the approved visual reference.
- Decision: Flat obsidian surfaces (`#0f1117`), hairline `#232732`
  divider, grouped sidebar, amber focused buttons, left-accented toasts,
  and an eleventh screen `SQLite Inspector` bound to `d`/`D`.
- Consequences: Visual rules in `UI_SPEC.md` §2–§3 are superseded by the
  root handoff spec; screen ids and 1–9/0 bindings are preserved.

---

## Pending / Proposed

_(none)_
