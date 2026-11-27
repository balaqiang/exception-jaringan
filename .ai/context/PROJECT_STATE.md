# NETCORE PROJECT STATE

Single source of truth for "where are we now". Updated by the
ORCHESTRATOR **only after verification** (tests actually run, review
passed). Never record a result that was not observed.

Last updated: 2026-11-27 — by ORCHESTRATOR

## Current Phase

Baseline implementation complete — Rich TUI, SQLite persistence,
pandas/NumPy analytics and the 11-screen keyboard interface.
Next: independent review and hardening (T-111 / T-503 style pass).

## Current Architecture

Layered Modular Monolith — `tui → application → domain`,
infrastructure implements application ports (DEC-005, DEC-016).
`pandas`/`numpy` are confined to `netcore.infrastructure.analytics`
(DEC-017). The TUI is Rich + a stdlib raw keyboard loop (DEC-016) with
the OpenCode flat dark aesthetic and an eleventh screen, SQLite
Inspector (DEC-018).

## Specification Status

| Document                     | Status   | Version |
| ---------------------------- | -------- | ------- |
| docs/PRD.md                  | Baseline | 1.1     |
| docs/ARCHITECTURE.md         | Baseline | 1.1     |
| docs/NETWORK_SPEC.md         | Baseline | 1.0     |
| docs/UI_SPEC.md              | Baseline | 1.1     |
| docs/UML.md                  | Baseline | 1.0     |
| .ai/agents/*.md (7 roles)    | Baseline | 1.1     |
| .ai/skills/*.md (8 skills)   | Baseline | 1.1     |
| .ai/context/DECISIONS.md     | DEC-001..DEC-018 | 1.1 |

## Completed

- Baseline docs, agent roles, skills and ADRs (including DEC-016..018).
- Domain: addressing, devices, interfaces, links, subnets, routing/LPM,
  ARP, MAC table, topology aggregate, forwarding engine, traceroute,
  traffic generator and typed error hierarchy.
- Persistence: 13-table SQLite schema, WAL, FK, migrator, UoW,
  repositories, sample-lab seeding and round-trip mapping.
- Application: frozen DTOs, ports, EventBus, 9 use-case services plus
  `AnalyticsService`.
- Analytics: read-only WAL snapshot reader, Pandas table pages/column
  stats/export, NumPy percentile/EMA/sparkline engine, data_version
  watcher and EventBus wake-up.
- TUI: OpenCode theme, responsive layout, raw keyboard reader (POSIX +
  Windows), 10 components, 11 views, modals, toasts and live SQLite
  Inspector.
- Tests: 94 passing, covering AT-01..AT-12, layer import guards,
  persistence round-trips, WAL external writes and headless renders.

## In Progress

- None.

## Planned

1. Independent code review against `.ai/agents/code-reviewer.md`.
2. Performance profiling of large event tables (LIMIT/OFFSET deep pages).
3. Optional VLAN/STP extensions — require a new decision and human
   approval.

## Known Issues in Original UTS Code

All five defects are fixed and covered by tests.

| # | Defect | Fix spec | Test |
| - | ------ | -------- | ---- |
| 1 | Routing uses string prefix matching. | NETWORK_SPEC §6.2, DEC-009 | AT-06 |
| 2 | TTL expiration is not handled correctly. | NETWORK_SPEC §6.3 step 3 | AT-07 |
| 3 | Switch forwarding matches destination IP. | NETWORK_SPEC §8.3 | T-109 / MAC-only engine |
| 4 | Link connectivity is not enforced. | NETWORK_SPEC §3.1, §4 | AT-09 |
| 5 | Bandwidth utilization is not implemented. | NETWORK_SPEC §10, DEC-011 | T-110 |

## Active Decisions

- DEC-001: Python 3.12+ (presentation clause superseded by DEC-016).
- DEC-002: SQLite persistence.
- DEC-003: Preserve the original OOP foundation.
- DEC-004: Simulation-only mode.
- DEC-005: Layered Modular Monolith with ports.
- DEC-006: No ORM — hand-written parameterised SQL.
- DEC-007: `ty` for static type checking.
- DEC-008: `NetworkTopology` is the aggregate root.
- DEC-009: Integer longest prefix match.
- DEC-010: Explicit simulated ARP.
- DEC-011: Capacity and utilization are separate.
- DEC-012: Deterministic simulation with injected clock/RNG.
- DEC-013: Synchronous in-process EventBus.
- DEC-014: pytest + headless renders (async clause superseded by DEC-016).
- DEC-015: Hierarchical multi-agent orchestration with skills.
- DEC-016: Rich + raw keyboard loop replaces Textual.
- DEC-017: pandas/NumPy confined to infrastructure analytics.
- DEC-018: OpenCode flat aesthetic + SQLite Inspector.

## Open Questions (need human input)

- OQ-01: Keep the legacy flat assignment files in `src/` indefinitely?
- OQ-02: VLAN support in a later phase?
- OQ-03: Lecturer export format (CSV / JSON / both)? Both are
  implemented; confirm which one is required.

## Blockers

- None.

## Next Task

T-504 — independent review and hardening pass. Re-run every quality
gate and record the review findings before marking the baseline released.

## Verification Status

| Check                         | Status        |
| ----------------------------- | ------------- |
| Implementation                | Complete      |
| `python -m pytest`            | PASS — 94 passed |
| `python -m ruff check .`      | PASS          |
| `python -m ruff format --check .` | PASS      |
| `ty check src/netcore`        | PASS          |
| Acceptance tests AT-01..AT-12 | 12 / 12       |
| Headless 120×36 / 100×30 / 80×24 renders | PASS |
| WAL external-write visibility | PASS          |

## Change History

| Date       | Agent        | Change |
| ---------- | ------------ | ------ |
| 2026-11-27 | ORCHESTRATOR | Initial specs, agent instructions, skills, decisions DEC-005..DEC-015. |
| 2026-11-27 | ORCHESTRATOR | DEC-016..018, full NetCore implementation, 11-screen Rich TUI, SQLite Inspector, 91 passing tests. |
