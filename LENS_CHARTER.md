# LENS Charter — 核心精神

**Document Status**: v1.0
**Document Type**: Foundational document — the "why" and the "what kind of"
**Authority**: This document is the **single mandatory read** for anyone (human or agent) working on LENS. Implementation Reference and Test Reference are optional.
**Audience**: Agents (primary), human implementers, reviewers

---

## 0. How to Read This Charter

This document defines what LENS **is** and what it **stands for**. It does not tell you how to write code. It tells you what to optimize for, what boundaries to respect, and what choices have already been made on your behalf.

If you (agent or human) need only one document before starting work, **this is that document**.

### 0.1 Authority Hierarchy

When sources conflict, the order of authority is:

```
Charter  >  Implementation Reference  >  Test Reference  >  Convention/habit
```

- **Charter** is normative. Deviation requires explicit human approval.
- **Implementation Reference** shows *one* working approach. You may propose better — surface the proposal, get approval, then proceed.
- **Test Reference** is illustrative. You are expected to derive the right tests for your task; the reference exists so you don't start from a blank page when stuck.
- **Convention/habit** is the weakest source. "We always did it this way" does not override anything above.

### 0.2 What this charter is NOT

- It is **not** a tutorial. It does not teach concepts; it assumes them or links out.
- It is **not** an API reference. Class names, function signatures, schema fields — all in Implementation Reference.
- It is **not** a project plan. Phases, deliverables, demos — those live in the whitepaper and roadmap docs.

### 0.3 Reading order on a fresh task

1. §1 困境與目標 — to understand why we exist
2. §3 架構總覽 — to understand the shape of the thing
3. §4 Design Principles — to understand the constraints on every decision
4. §5 開發與部署模型 — to understand the environment
5. Then optionally consult Implementation Reference for the specific module you are touching

---

## 1. 困境與目標

### 1.1 現況：AP 的結構性限制

The library build pipeline at TSMC's Standard Cell Library Automation Team has been driven by **AP (AutoPilot)** for over a decade. AP works — it has produced thousands of libraries, kept production flowing, and survived staff turnover. We do not propose to replace it.

But AP carries the assumptions of its original design era — assumptions that no longer match today's needs:

- **AP couples execution, scheduling, state, and logging into one monolithic process.** Any change touches all four. Even adding a new field to its dashboard requires understanding the whole.
- **State lives in CSV files and ad-hoc logs scattered across NFS.** There is no single source of truth for "what is this build doing right now." Engineers reconstruct state by reading files, calling colleagues, and inferring from indirect signals.
- **Granularity is hardcoded.** AP's smallest unit is `flow × branch`. There is no way for the system to express "this PVT failed but those PVTs succeeded" or "rerun only this cell" — the data structures don't admit that.
- **There is no event stream.** Tools that want to consume AP's behavior (dashboards, agents, cross-team integrations) have no contract to consume against. Each builds its own ad-hoc poller.

These are not bugs. AP works as designed. The problem is that the design no longer fits the world.

### 1.2 三個維度的擴展受阻

The team and the broader organization want to extend the build pipeline in three directions. **Each of them is blocked by the same root cause** — AP's monolithic, state-coupled, fixed-granularity design.

**往上 (Upward — cross-library, cross-project)**
Leadership wants visibility across all libraries in the division: which are healthy, which are slipping, where are the bottlenecks. Today this requires manual aggregation across CSVs and Teams messages. **AP cannot tell you the health of the library it isn't running.**

**水平 (Horizontal — cross-team, cross-department)**
Downstream teams (QC, IP production, methodology) need structured access to build state. Today this happens through email, Teams, and ad-hoc scripts that screen-scrape AP's dashboards. **There is no contract for them to consume against.**

**往下 (Downward — fine-grain, per-PVT, per-cell)**
The team wants to express dependencies and rerun granularity at the PVT and cell level — to avoid redoing work, to accelerate iteration, to support modern AI-assisted analysis. Today everything is `flow × branch`. **The data model itself forbids finer granularity.**

These three directions look different but share a single solution: **structured events at the right granularity, owned by a platform separate from AP itself.**

### 1.3 為什麼是平台、不是工具

We could write another tool. We could write a dashboard, or a parser, or a notifier. We have written many such tools. They live in `/home/$user/scripts/`. They break when AP changes. They compete for the same data with slightly different interpretations. They are individually useful and collectively a mess.

What's missing is a **platform** — a shared substrate that:

- Owns the structured representation of build state, **once, for everyone**
- Lets new consumers (dashboards, agents, downstream teams) plug in **without modifying AP**
- Outlives any individual tool built on top of it
- Is small enough that one person can hold it in their head, but extensible enough that the team can grow into it

The distinction between "tool" and "platform" is not size. It is **whether others build on top of it without permission**. LENS is the latter.

### 1.4 LENS 的承諾

LENS makes four commitments. Every architectural decision in this charter traces back to one of these.

**Commitment 1 — We do not change AP.**
AP continues to fly the plane. LENS observes from outside, derives meaning, and surfaces it. AP's source code is not modified. AP's behavior is not altered. AP can be turned off; LENS goes dark gracefully.

**Commitment 2 — Events are the source of truth.**
Build state lives in an append-only event log, not in a database row that can be overwritten. Every dashboard, every projection, every metric is *derived* from that log. The log is replayable, auditable, and shared.

**Commitment 3 — Granularity is data, not schema.**
Build, library, flow, PVT, cell — all share one node abstraction, distinguished by a field, not by a table or class. Adding a finer level is data work, not architecture work.

**Commitment 4 — The platform is for consumers we have not yet met.**
We design as if a future agent, a future cross-team integration, a future analytics use case is going to consume our events. We don't know what they need. We make our event schema legible, our APIs declarative, our state replayable — so that future consumers can be wired in without a rewrite.

### 1.5 What LENS is not trying to solve (yet)

It is as important to be clear about what LENS does **not** promise:

- LENS does not (in Phase 1) **execute** flows. AP still does. LENS observes execution.
- LENS does not (in Phase 1) replace any existing tool or workflow. It runs alongside.
- LENS does not promise incremental run, content-addressed caching, agent-driven orchestration, or per-cell dependency analysis **in Phase 1**. These are downstream consequences once the foundation exists.
- LENS does not promise to reduce headcount or replace human judgment. It surfaces information; humans and agents still decide.

If a request to LENS sounds like "and also could it...", the default answer is: **not in this phase. The foundation comes first.**

---

## 2. Naming Convention

### 2.1 Platform Name: LENS

The platform is named **LENS** — a backronym for **L**ayered **E**vent-driven **N**avigation **S**ystem.

The name carries forward the spirit of AP (AutoPilot) without inheriting its limitations. In aviation's progression, the layer above autopilot is the **Navigation System** — it does not replace the pilot, it gives the pilot situational awareness, route planning, and visibility into the broader picture. LENS plays the same role for our library build:

- AP continues to fly the plane (execute flows)
- LENS sees the whole sky (observe, record, project, surface)

The four letters of LENS each carry a design principle:

| Letter | Meaning | Maps to |
|---|---|---|
| **L**ayered | 6-layer architecture (L0–L5) | DP-3 (Granularity is Data, Not Schema) — fractal hierarchy |
| **E**vent-driven | Events are the source of truth | DP-2 (Append-only Truth, Derived Views) |
| **N**avigation | A higher view than autopilot | The "what comes after AP" semantic position |
| **S**ystem | A coordinated whole, not a tool | Platform-as-substrate philosophy |

When pitching to leadership, the elevator version is:
> "LENS is the navigation system that comes after autopilot — layered, event-driven, observing every library build at every scale."

### 2.2 Code Identifiers

The LENS brand maps to code identifiers uniformly — there is no separate "code name" vs "product name":

| Surface | Identifier |
|---|---|
| Platform brand (docs, exec pitch) | **LENS** |
| Python package | `lens` |
| Repository | `lens` |
| Kafka topic prefix | `lens.*` (e.g., `lens.events`) |
| CLI entry points | `lens-observer`, `lens-projection`, `lens-api` |
| PostgreSQL table prefix | `lens_*` |
| Configuration env prefix | `LENS_*` |

Internal modules follow normal Python conventions (`snake_case`, descriptive names like `lens.observer`, `lens.backbone`, `lens.projection`). DP-9 governs only the platform name itself; it does not impose a four-letter rule on internal modules.

### 2.3 Future Component Names

When the platform grows beyond Phase 1 (e.g., L1 Orchestration Core in Phase 2+), new top-level components MAY be given their own brand-level names if doing so adds clarity. Such names SHOULD follow DP-9 (real English word + meaningful backronym) but are decided **at the time of need**, in their own context — not pre-allocated here.

---

## 3. 架構總覽

### 3.1 The 6-layer Architecture

LENS organizes its responsibilities into six layers. Each layer has a single primary concern, and layers depend only on those below them.

```
┌─────────────────────────────────────────────────────────────┐
│  L5 · Experience — Dashboard, CLI, agent UIs                │
├─────────────────────────────────────────────────────────────┤
│  L4 · Agents & Intelligence — validators, debug assistants  │
├─────────────────────────────────────────────────────────────┤
│  L3 · Query & Projection                                    │
│      Read-optimized views derived from the event log        │
├─────────────────────────────────────────────────────────────┤
│  L2 · Event Backbone                                        │
│      The single source of truth: append-only event log      │
├─────────────────────────────────────────────────────────────┤
│  L1 · Orchestration Core (Phase 2+)                         │
│      Pull-based evaluation, content-addressed cache         │
├─────────────────────────────────────────────────────────────┤
│  L0 · Observer & Adapter                                    │
│      Translates legacy AP / OBF state into structured events│
└─────────────────────────────────────────────────────────────┘
```

**Phase 1 builds**: L0 (Observer), L2 (Event Backbone), L3 (Projection), L5 (Dashboard).
**Phase 2+ adds**: L1 (Orchestration Core).
**Phase 3+ adds**: L4 (Agents).

### 3.2 Why this shape

Three structural choices shape the layering:

**Layer 0 is the only place that touches AP.** Everything above L0 only sees structured events, not AP itself. This isolation is what makes Commitment 1 (we do not change AP) operationally enforceable: if no module above L0 imports anything AP-shaped, no module above L0 can accidentally couple to AP.

**Layer 2 is the single source of truth.** L3 is *derived* from L2. L4 *consumes* L2 (and emits back to L2). L5 *displays* projections of L2. There is no way to short-circuit and write directly to L3 — that would create a state that cannot be reproduced by replaying events.

**Layer 1 is missing in Phase 1, and that's intentional.** Most platforms try to "do everything" on day one, including their own execution engine. LENS deliberately delays L1 until the system has earned the right to it — until L0/L2/L3/L5 are battle-tested with real data. Phase 1 produces value (a dashboard) without writing a single line of execution code.

### 3.3 Information flow

Data moves through LENS in one direction:

```
AP / OBF (legacy)
    ↓ observed by
L0 · Observer
    ↓ emits structured events to
L2 · Event Backbone (Kafka)
    ↓ consumed by
L3 · Projections (PostgreSQL views)
    ↓ queried by
L5 · Dashboard / CLI
```

Agents (L4) attach to L2 as additional consumers; their outputs (validation results, anomaly flags) become **new events** on the same backbone. They do not bypass it.

### 3.4 What you, the implementer, are building

For Phase 1, you are building:

- **An observer** that watches AP without modifying it (L0)
- **An event schema** that captures build state at the right granularity (L2)
- **A pipeline** that moves events from observer to backbone to projections (L2 + L3)
- **A dashboard** that renders projections for human consumption (L5)

You are *not* building L1 (orchestration), L4 (agents), incremental run, content-addressed cache, or per-cell granularity in Phase 1. Those exist in this charter so that what you build in Phase 1 **does not foreclose them**.

---

## 4. Design Principles

These are the standing constraints on every design and implementation decision. They are numbered for stable reference — when discussing or reviewing, cite by number ("DP-3 says granularity is data; this PR makes it schema, that's a violation").

### DP-1: Non-invasive Observation

**Statement**: New platform components MUST observe legacy AP without modifying it. No source-code changes to AP, no script-level hooks injected into OBF flows, no wrapping that changes flow execution semantics.

**Why**: Legacy AP is brittle, originally-authored by someone no longer maintaining it, and embedded in production-critical paths. Any modification carries regression risk that exceeds the value of any single feature we'd add. Non-invasive observation lets us extract value from AP without taking on responsibility for maintaining it.

**How to apply**:
- Observers read AP's existing outputs (CSV dashboards, log files, status files)
- Polling is acceptable; injection is not
- If we cannot observe a state we want, we accept that limitation OR coordinate with AP's owner — never patch AP ourselves
- Write-back paths to AP are forbidden; we may emit advisories but not mutate AP state

**How to detect violation**: Search the codebase for any path that opens a file under AP's directory in write mode. Search for any `subprocess` call that runs an AP-internal binary with arguments that aren't `--read-only` equivalents.

### DP-2: Append-only Truth, Derived Views

**Statement**: The system of record for build state MUST be the event log (Kafka). All other data stores (PostgreSQL projections, in-memory caches, dashboards) are **derived projections** that can be rebuilt by replaying events.

**Why**: Mutable state hides history. When something goes wrong, you cannot ask "what did this look like an hour ago?" Append-only event logs give us free time-travel, free debuggability, free new-projection capability without schema migration.

**How to apply**:
- Events are never modified after being produced (no `UPDATE` on events)
- Projections must be rebuildable: deleting a projection table and replaying events produces the same data
- New consumers can be added without coordinating with existing consumers
- Mutable state in code (instance variables, module-level dicts) is allowed only as derived caches that can be re-derived from events

**How to detect violation**: A projection table that cannot be safely truncated and rebuilt is a violation. Any consumer that relies on Kafka being unavailable or events being deleted is a violation.

### DP-3: Granularity is Data, Not Schema

**Statement**: The level of granularity (build, library, flow, PVT, cell) MUST be a field on the data, never a dimension of the schema. Code that hardcodes a specific level is a violation.

**Why**: Stakeholders will ask for finer (per-PVT, per-cell) and coarser (cross-library, cross-project) views over time. If granularity is baked into table structures, every new level requires a migration. If granularity is a column value, new levels are zero-migration.

**How to apply**:
- The `level` field on events takes one of `["build", "library", "flow", "pvt", "cell"]`
- PostgreSQL projections have `level` as a column with index, not separate tables per level
- Query interfaces accept `level` as a filter parameter, not as a path component
- Future levels can be added by extending the enum, no breaking changes required

**How to detect violation**: Search for tables named after specific levels. Search for code that switches on level via `if/elif` chains for fundamentally similar logic.

### DP-4: Boring Tech First

**Statement**: When choosing a library, framework, or pattern, the option already in use within the organization or the wider industry mainstream MUST be preferred over a newer, more clever, or more "best-of-breed" option, **unless** there is a specific failure mode the boring option cannot address.

**Why**: We are a small team in a large organization. Every novel technology adds onboarding cost, support cost, and political resistance. The cost of "this is unfamiliar" is often invisible at decision time and crushing at maintenance time.

**How to apply**:
- Use Kafka (already in-house) over NATS, even if NATS is "lighter"
- Use PostgreSQL (already in-house) over MongoDB or specialized stores
- Use Python (team familiar) over Rust/Go for orchestration logic
- Prefer SQLAlchemy over a custom DAL
- Prefer FastAPI over building HTTP routing manually

**How to detect violation**: Adding a new dependency to `pyproject.toml`. Every addition triggers a justification: what does the boring alternative fail at?

### DP-5: Test-list Before Code

**Statement**: Every module MUST have its test list defined and approved before any production code for that module is written. The test list is the source of truth for what the module does.

**Why**: TDD without a planned test list devolves into reactive testing — writing tests after each piece of code, mirroring implementation. A planned test list, written from intent, ensures tests assert *behavior the design demands*, not *behavior the code happens to have*.

**How to apply**:
- Write the test list first (the Test Reference document offers starting templates per module, but you may extend or rewrite)
- During implementation you may discover missed cases; add them with explicit notes
- Sample test cases in the Test Reference are illustrations — your context may demand different specifics

**How to detect violation**: A `feat:` commit with no preceding `test:` commit. A function with public surface area but no test that exercises it.

### DP-6: Failure is Loud and Specific

**Statement**: When something fails, the system MUST raise a domain-specific exception, log a specific error, or exit with a non-zero code carrying a meaningful message. Silent fallbacks, generic exceptions, and swallowed errors are forbidden.

**Why**: Platforms run for years. Bugs found in development are cheap; bugs found three years later in a misbehaving downstream service are expensive. Loud failures move bugs left in time. Silent failures defer them.

**How to apply**:
- Each module defines its own exception hierarchy
- Bare `except:` and `except Exception:` are forbidden (use specific types)
- Documented retry/buffer mechanisms (e.g., the producer's local-buffer-on-failure) are NOT silent fallbacks: they are documented, observable via metrics, and emit structured events about their state
- API endpoints return 4xx/5xx with structured error bodies, never empty 200 with `{"data": null}`

**How to detect violation**: Grep for `except Exception` without a re-raise or specific handling. Search API code for `return None` in an error path that should return a structured error.

### DP-7: Spec Drives, Code Follows

**Statement**: When code and the relevant document disagree, the document is the source of truth. If the code is right and the document is wrong, **update the document first**, then update the code. Do not let docs drift silently.

**Why**: A document that lags reality is worse than no document — it gives false confidence. Maintaining the docs as living documentation is part of the engineering discipline, not a separate task to do later.

**How to apply**:
- Whenever you find yourself coding around a doc, stop. Either the doc is wrong (update it as a `docs:` commit, ideally before the related `feat:` commit) or your understanding is wrong (re-read)
- PR reviews should check: do the relevant Charter / Implementation / Test sections describe what this PR builds?
- Doc updates SHOULD precede or accompany code changes; trailing updates are acceptable but flagged

**How to detect violation**: A PR labeled `feat:` with no `docs:` companion AND introducing behavior not covered in any document. A document section that contradicts the current behavior of the corresponding module.

### DP-8: Replaceable Adapters at I/O Boundaries

**Statement**: Every I/O boundary — Kafka, PostgreSQL, HTTP clients, LLM endpoints, file system, time, randomness — MUST be hidden behind an interface (Python `Protocol` or `ABC`) defined in the consuming module. Production code MUST target the interface, never a vendor SDK or specific driver directly.

**Why**: The primary motivation is **testability**, not future vendor switching. When I/O is interface-isolated:
- Unit tests can use in-memory fakes — no testcontainers, no Docker, no network
- Tests run in milliseconds, not seconds
- Tests are deterministic — no flakes from external service quirks
- Tests can simulate failure modes (network errors, slow responses, malformed payloads) trivially

The bonus is that future replacement (swapping aiokafka for confluent-kafka, PostgreSQL for another store, vendor LLM A for vendor LLM B) becomes a config change instead of a refactor. But this is the bonus, not the goal — chase it as a side effect of caring about testability.

**How to apply**:

1. Define the interface in the module that uses it, not in a global `interfaces/` package. Co-locate.
2. Production code targets the interface (`Protocol` or `ABC`).
3. Tests use an in-memory fake living next to the test or in the module itself.
4. Wire concrete implementation only at app composition root (e.g., `lens.api.app`, the entrypoint). Never `import aiokafka` or `import sqlalchemy` inside business logic modules.
5. Configuration selects the implementation.

Adapters required by Phase 1: EventBus (Kafka), ProjectionStore (PostgreSQL), Clock (for deterministic time in tests), HTTPClient. Phase 2+ adds ArtifactStore (NFS + sha256). Phase 3+ adds LLMClient.

**How to detect violation**:
- Any business-logic module imports `aiokafka`, `sqlalchemy`, `httpx`, vendor SDK directly → violation
- Any unit test that requires testcontainers / docker / network to run → violation (this should be an integration test, not a unit test)
- `datetime.now()` or `time.time()` called in business logic without injection → violation
- Tests that mock with `unittest.mock.patch('module.aiokafka')` → violation (use a real fake instead)

### DP-9: Naming Carries Meaning

**Statement**: The platform name MUST be a valid English word AND a backronym whose expansion describes the system's actual responsibility. Random acronyms, marketing-only names, and forced backronyms are forbidden.

**Why**: A name carried for 5+ years shapes how everyone — engineers, executives, future hires — thinks about the system. A name with structural meaning in its letters acts as **constant reinforcement of the architecture**. When someone asks "what does LENS do?", the answer is in the name itself.

**How to apply**: see §2 Naming Convention — operationalized as **LENS** = Layered Event-driven Navigation System.

**How to detect violation**: A name whose acronym expansion does not describe the system's actual responsibility, or which is not a real English word. (This rule applies to platform-level brand naming. Internal modules follow normal Python conventions and are not bound by it.)

---

## 5. 開發與部署模型

Development happens **outside** the production environment. The production environment is air-gapped and constrained; the development environment is not. The two are bridged by GitHub.

```
┌─────────────────────────┐                  ┌─────────────────────────┐
│  External Dev Env       │                  │  Internal Workstation   │
│  (有網路、Linux/bash)    │                  │  (air-gapped, tcsh)     │
│                         │                  │                         │
│  AI agent + Brian       │                  │  Brian (deploy + run)   │
│  ↓                      │                  │  ↑                      │
│  Code, tests, CI        │   git push       │  Code, configs          │
│  ↓                      │  ──────────→    │                         │
│  GitHub  ───────────────┼──────┐    ┌──────┼─── git pull             │
│                         │      │    │      │                         │
└─────────────────────────┘      └────┘      └─────────────────────────┘
                                  GitHub
```

### 5.1 Implications for the implementer

**The agent never touches production.** All code is delivered via GitHub. Brian deploys.

**Production-specific concerns are configuration, not code.** Kafka cluster endpoints, internal LLM URLs, license servers — these are wired at deployment by Brian, not coded into modules. DP-8 (Replaceable Adapters) is what makes this work: code targets interfaces; deployment chooses concrete adapters via `lens.config.settings`.

**Tests run in dev with fakes (unit) or testcontainers (integration).** Production validation happens at deployment via smoke tests.

**Dependencies must be reviewable.** When adding a new entry to `pyproject.toml`, flag it explicitly in the PR for human review — this triggers a check on whether the package is available via the internal mirror.

### 5.2 Portability constraints

The agent develops in a standard Linux + bash environment with internet access. The production environment differs, but the agent is insulated from those differences by DP-8. The few portability rules the agent MUST follow:

- **Code MUST be Python 3.12+ pure** — no shell-out for logic that could be Python
- **Any shell script (Makefile target, Docker entrypoint, CI script) MUST be POSIX `sh`-compatible** — start with `#!/bin/sh`, no bash-isms (`[[`, array syntax, etc.). Verify with `shellcheck -s sh`.
- **No hardcoded URLs, hostnames, or credentials** — everything comes from `lens.config.settings`
- **No assumption about which adapter is wired in production** — code targets the interface, not a specific implementation

If the agent finds itself writing code that depends on production specifics, it is violating DP-8. Refactor through an adapter.

---

## 6. Glossary

This glossary covers terms specific to TSMC internal systems, organizational structure, or naming conventions. **Industry-standard concepts** (event sourcing, content-addressed storage, projection, etc.) are not listed here — see standard references.

### 6.1 Internal Systems & Tools

| Term | Full Form | Definition |
|---|---|---|
| **AP** | AutoPilot | The legacy flow scheduling system; LENS's predecessor. Originally authored by an engineer no longer the primary maintainer. Operates on flow × branch granularity, with state stored in CSV-style dashboards. |
| **OBF** | (internal acronym) | Umbrella term for the production flow programs that AP orchestrates. Encompasses individual `step` and `kit` definitions for standard cell library generation. |
| **SOS** | ClioSoft SOS | The version-control system in use for production code (replaces git for OBF and AP code). Has per-user workspace semantics distinct from git's branch-and-merge model. |
| **LSF** | Load Sharing Facility | The job scheduler for compute jobs. AP submits to LSF; resource accounting and license assignment happen through LSF. |
| **SMAK** | (internal acronym) | A semantic search and knowledge graph MCP server developed internally. Functions as institutional memory for agents. Authored by Brian. |
| **DevLedger** | — | A YAML-based feature state tracking CLI; tracks the lifecycle of platform features (proposed / in-progress / shipped / deprecated). Authored by Brian. |
| **all-might** | — | An internal agent harness framework, separately developed. LENS and all-might are independent tools that may integrate at points where LENS exposes events for agent consumption (per L4 Agent Layer in the architecture); LENS is **not** a sub-application of all-might. |

### 6.2 Roles & Ownership Concepts

| Term | Definition |
|---|---|
| **flow** | A program / definition (the script and spec living in the repo). "Flow" is **not** a runtime instance; it is the static definition. |
| **flow owner** | The code owner — the engineer who maintains a flow's definition. Concerns: code quality, regressions across builds, structural improvements. |
| **KG** | Kit Generation. A single execution instance of a build (what we'd call "a build" or "an instance" in industry vocabulary). |
| **KG owner** | The engineer who initiated a specific KG. Concerns: did *my* build succeed, *why* did it fail, when will it complete. |
| **library build** | A complete generation of a standard cell library; involves dozens of flows running over hours-to-days. |
| **library** | A standard cell library — the deliverable artifact. |
| **PVT** | Process / Voltage / Temperature corner. A specific operating condition under which a cell is characterized. A single library build typically covers multiple PVTs. |
| **cell** | An individual standard cell within a library (e.g., `inv_x1`, `nand_2`). The finest meaningful granularity for dependency tracking. |

### 6.3 LENS-specific Naming

| Term | Definition |
|---|---|
| **L0 / L1 / L2 / L3 / L4 / L5** | LENS's six architectural layers; see §3. |
| **Event Backbone** | Synonym for L2; specifically the Kafka-based event infrastructure. |
| **Projection** | A read-optimized view of the event stream, materialized in PostgreSQL. Each projection is independent and rebuildable. |
| **Observer** | Synonym for L0; specifically the components that watch legacy AP state and emit structured events. |
| **build_id** | Identifier for a single KG instance, used as Kafka partition key and as foreign key in projections. NOT to be confused with the term "build" used loosely in CI/CD contexts. |
| **action cache** | (Phase 2+) The content-addressed cache mapping `input_hash → output_hash`. Reuses Bazel's "action" terminology. |

### 6.4 Organizational Context

| Term | Definition |
|---|---|
| **division / 事業部** | Organizational unit two levels above Brian's team. Cross-division integration is non-trivial; same-division is easier. |
| **跨上下游部門** | Cross-functional teams in the broader workflow chain (e.g., QC team, IP production team). They are users / observers of library build state, not authors. |
| **executive dashboard** | The Phase 1 deliverable; the primary surface for division-level leadership to monitor library build health 24/7. |

---

## 7. Charter Versioning

This charter is intentionally short. Major rewrites are signaled by version bumps. Any change to a Design Principle, the architectural shape, or the LENS commitments requires explicit human approval and a version bump.

- **v1.0** — Initial separation of charter from implementation reference. Distilled from `implementation_spec_v0.6.md` §0–§3, §15 Glossary, plus newly-written §1 困境與目標.

---

*— End of LENS Charter v1.0 —*
