# Living Architecture Harness MVP — CodeGraph-First Reconciliation Plan

## 1. Goal

Build a lightweight coding harness where architecture evolves while coding, but never silently.

The key assumption is:

```text
CodeGraph = source of truth for observed architecture
Architecture docs = source of truth for intended architecture
```

The harness should make every feature go through this loop:

```text
Feature request
  -> targeted CodeGraph query
  -> reconciliation with intended architecture docs
  -> architecture patch
  -> scoped coding
  -> tests + architecture validation
  -> updated architecture docs/state
```

The goal is not full design upfront. The goal is to keep dependency structure, domain model, and data contracts understandable as the codebase grows.

---

## 2. Core Operating Rules

### Rule 1 — CodeGraph is the source of truth for observed architecture

Use CodeGraph to answer:

```text
- What does the code currently contain?
- Which modules depend on which modules?
- Which symbols, classes, and functions are connected?
- What is the blast radius of this change?
- Which domain classes and data contracts already exist?
```

Do not treat `/architecture/*.md` as an exact mirror of the current codebase. They are design memory, not ground truth.

Use CodeGraph only through targeted questions:

```text
Main MCP agent: use `codegraph_explore`
Non-MCP/subagent workflow: use `codegraph explore "<targeted query>"`
```

Do not repeatedly tell agents to “run CodeGraph.” CodeGraph is already wired into the agent after setup and should be queried only when architecture context is needed.

---

### Rule 2 — Architecture docs express intended architecture

Architecture docs store what the system is trying to preserve:

```text
- intended module boundaries
- allowed and forbidden dependencies
- domain model decisions
- data contract decisions
- accepted architecture tradeoffs
- known risks
```

The docs should stay compact. They should not duplicate CodeGraph.

Good architecture docs answer:

```text
What should be true?
Why was this decision made?
Which boundaries should not be crossed?
Which domain concepts are first-class?
Which data contracts are official?
```

CodeGraph answers:

```text
What is true in the code right now?
```

---

### Rule 3 — Use a Reconciliation Gate before planning

Users may modify the repo outside the harness through bug fixes, refactors, experiments, or hotfixes.

Because CodeGraph tracks the codebase, this is not mainly a “stale CodeGraph” problem. It is a reconciliation problem:

```text
Observed architecture from CodeGraph
vs.
Intended architecture from /architecture docs
```

Before planning a feature, the Architect must ask one targeted CodeGraph question about the affected area and compare it with the intended docs.

Decision labels:

```text
ALIGNED
  Observed architecture matches intended architecture enough to continue.

DOC_DRIFT_ACCEPTED
  Code changed outside the harness, but the change is acceptable.
  Update architecture docs/ADR/state before or together with the feature patch.

CODE_DRIFT_HARMFUL
  Code changed outside the harness and violates intended architecture.
  Propose a refactor/reconciliation patch before feature work.

UNCLEAR_DRIFT
  The mismatch may be acceptable or harmful.
  Ask a human to decide before coding.
```

Do not solve drift by reading the whole repo. Query CodeGraph narrowly and update only affected architecture artifacts.

---

### Rule 4 — Architecture changes require a patch

Before implementation, every meaningful feature needs a compact architecture patch covering:

```text
- reconciliation decision
- affected modules
- dependency changes
- domain class changes
- data contract changes
- allowed files
- forbidden changes
- required tests
```

The coding agent implements only the approved patch.

---

### Rule 5 — Prefer domain classes over module-level business functions

Core business behavior should live in domain classes, not scattered module-level functions.

Allowed module-level functions:

```text
- tiny pure helpers
- CLI/framework entrypoints
- simple composition functions
- temporary migration wrappers
```

If a function contains domain rules, state transitions, validation policy, or repeated business logic, propose a domain class or method.

Example:

```text
Bad:
calculate_route_risk(route, robots, obstacles)

Better:
RouteRiskPolicy.evaluate(route, robots, obstacles)
```

---

### Rule 6 — Data contract classes are first-class architecture artifacts

Whenever data crosses a boundary, represent it with a dedicated data contract class.

Boundaries include:

```text
module, API, socket, queue, file, service, process, external tool
```

Agents may create, expand, merge, split, rename, and version contract classes, but only through an approved architecture patch.

Contract lifecycle operations:

```text
CREATE  — new boundary data appears
EXPAND  — new required/optional field is needed
MERGE   — duplicated DTO/payload classes mean the same concept
SPLIT   — one contract mixes unrelated boundary concerns
RENAME  — name no longer reflects meaning
VERSION — breaking boundary change is required
```

---

### Rule 7 — Keep domain classes and contracts separate

| Type | Purpose | Location |
|---|---|---|
| Domain class | Business concepts, behavior, invariants | `src/domain/` |
| Data contract class | Stable payload shape across boundaries | `src/contracts/` |

Recommended flow:

```text
external payload -> contract class -> mapper/application layer -> domain class
```

Do not put business logic in contract classes. Do not expose raw domain objects as external payloads unless explicitly approved.

---

## 3. Token Budget

### CodeGraph call budget per feature

| Phase | Budget |
|---|---:|
| Reconciliation + patch planning | 1 targeted query |
| Scoped coding | 0 by default, max 1 emergency query |
| Validation | 1 targeted query on changed files/symbols |

If an agent needs more, it must stop and explain why.

### Forbidden token-wasting behavior

Agents must not:

```text
- ask CodeGraph to explain the whole repo during a feature task
- grep/read the whole repo after CodeGraph already answered
- pass raw CodeGraph output to every subagent
- copy long source bodies into architecture docs
- create long ADRs for small changes
- generate diagrams with every file and symbol
- re-query CodeGraph with the same broad question after a usable answer
```

### Compact context format

Pass summaries like this, not raw tool output:

```md
## Relevant Architecture Context

Observed from CodeGraph:
- `module_a -> module_b`: reason / symbol edge
- `ClassName`: responsibility, key methods
- `ContractName`: boundary, key fields

Intended from architecture docs:
- allowed dependencies:
- forbidden dependencies:
- intended domain classes:
- intended data contracts:

Reconciliation decision:
- ALIGNED / DOC_DRIFT_ACCEPTED / CODE_DRIFT_HARMFUL / UNCLEAR_DRIFT

Known risks:
- risk
```

---

## 4. Minimal Repository Artifacts

Create these files:

```text
/architecture
  state.yaml               # last reconciliation/validation metadata; not source of truth
  architecture.md          # intended module map, key boundaries, risks
  boundaries.yaml          # intended allowed/forbidden dependencies
  domain-model.md          # intended domain classes and refactor candidates
  data-contracts.md        # official contracts and raw payload risks
  graph-notes.md           # compact CodeGraph observations, only when useful
  diagrams/current.mmd     # high-level diagram, not every symbol
  patches/                 # approved architecture patches
  validation/latest-report.md

.claude/agents          # self-contained custom subagent defs (frontmatter + prompt body)
  surveyor.md
  architect.md
  builder.md
  inspector.md
```

Optional later:

```text
/architecture/adr/
/architecture/snapshots/
```

Important:

```text
Do not use architecture docs as a full code index.
CodeGraph already serves that role.
```

---

## 5. Recommended Source Layout

```text
/src
  domain/        # domain entities, value objects, policies, domain services
  contracts/     # data contracts crossing boundaries
  application/   # use cases and orchestration
  adapters/      # DB/API/framework/external tools
  shared/        # small primitives and utilities
```

Start simple. Do not force this layout onto a legacy repo all at once.

---

## 6. Minimal Agents

## Agent 1 — Architect

Purpose: reconcile observed architecture with intended architecture, then propose the smallest safe architecture evolution before coding.

Inputs:

```text
- feature request
- architecture.md
- boundaries.yaml
- domain-model.md
- data-contracts.md
- state.yaml
- one targeted CodeGraph query about the affected area
```

Required output:

```text
/architecture/patches/YYYY-MM-DD-feature-name.md
```

Patch must include:

```text
1. observed architecture from CodeGraph
2. intended architecture from docs
3. reconciliation decision
4. affected modules
5. dependency changes
6. domain class changes
7. data contract changes
8. files allowed to edit
9. tests required
10. risks
11. approval checkbox
```

Hard rules:

```text
- CodeGraph wins for what exists now
- architecture docs win for what should be preserved
- if observed and intended architecture conflict, classify the mismatch before coding
- define/reuse a contract class for new boundary data
- define/update a domain class for new business behavior
- do not propose broad repo exploration
- do not write implementation code
```

---

## Agent 2 — Builder

Purpose: implement only the approved patch.

Inputs:

```text
- approved patch
- compact architecture context
- listed files
- listed tests
```

Hard rules:

```text
- edit only approved files
- use only approved dependencies
- no hidden architecture changes
- no raw dict/list crossing boundaries
- no duplicate contract class if reuse/merge is possible
- no new module-level business function for domain behavior
- do not call CodeGraph unless the patch is ambiguous
```

If the patch is insufficient, stop and request a patch revision.

Output summary:

```text
- files changed
- domain classes changed
- data contracts changed
- dependencies added/removed
- tests added/updated
- patch assumptions
```

---

## Agent 3 — Inspector

Purpose: verify the implementation matches the approved patch and intended architecture.

Inputs:

```text
- approved patch
- git diff file list
- test results
- one targeted CodeGraph query over changed files/symbols
```

Checks:

```text
- observed dependencies match the approved patch
- no forbidden dependency edge
- no unapproved dependency edge
- no new cycle
- no public interface drift outside patch
- no raw boundary payload
- no duplicated contract class
- contract create/expand/merge/split was approved
- business logic is in domain classes/methods
- required tests pass
- architecture docs updated only for accepted intended changes
- state.yaml updated after accepted validation
```

Decision labels:

```text
ACCEPT
ACCEPT WITH DOC UPDATE
NEEDS PATCH REVISION
REJECT: ARCHITECTURE VIOLATION
REJECT: CONTRACT VIOLATION
REJECT: DOMAIN MODEL VIOLATION
REJECT: TEST FAILURE
```

---

## 7. Optional Agent — Surveyor

Use this only occasionally, not every feature.

When:

```text
- first setup
- weekly review
- after 5-10 merged changes
- after a large human refactor
- when repeated reconciliation mismatches appear
```

Budget:

```text
1-2 targeted CodeGraph queries
```

Output updates:

```text
architecture.md
boundaries.yaml
domain-model.md
data-contracts.md
graph-notes.md
diagrams/current.mmd
```

Survey rule:

```text
Do not summarize the whole repo.
Summarize only stable architecture boundaries and risks worth preserving.
```

---

## 8. Architecture Patch Template

```md
# Architecture Patch: <Feature Name>

## Feature Request

<original request>

## Observed Architecture from CodeGraph

Affected modules:
- `module`: current responsibility, key files

Observed dependencies:
- `a -> b`: reason / symbol edge

Observed domain classes:
- `ClassName`: current responsibility

Observed data contracts:
- `ContractName`: boundary, key fields

## Intended Architecture from Docs

Relevant intended boundaries:
- rule

Relevant intended domain model:
- class / policy / invariant

Relevant intended contracts:
- contract / boundary

## Reconciliation Decision

Decision:
- ALIGNED / DOC_DRIFT_ACCEPTED / CODE_DRIFT_HARMFUL / UNCLEAR_DRIFT

Action:
- continue / update docs / refactor first / ask human

## Proposed Change

### Module Changes

- Create/modify/remove: reason

### Dependency Changes

Allowed:
- `module_a -> module_b`: reason

Forbidden:
- `module_x -> module_y`: reason

### Domain Model Changes

- Create/expand/merge/split/move behavior: reason

### Data Contract Changes

- Create/expand/merge/split/rename/version: reason

### Files Allowed to Edit

- `path/to/file`

### Tests Required

- domain behavior test
- contract validation test
- boundary/integration test

## Risks

- risk:

## Approval

- [ ] Approved
```

---

## 9. Minimal `state.yaml`

```yaml
last_reconciled_commit: "<git-sha>"
last_validated_commit: "<git-sha>"
last_validation_time: "YYYY-MM-DDTHH:MM:SS"
last_reconciliation_decision: "ALIGNED"
last_codegraph_query_scope:
  - "src/path_or_module"
notes:
  - "State is metadata only. CodeGraph is source of truth for observed architecture."
  - "Architecture docs are intended architecture, not a full code index."
```

Use `state.yaml` to track process status, not to decide what the code currently contains.

---

## 10. Minimal `boundaries.yaml`

```yaml
modules:
  domain:
    path: "src/domain/**"
    responsibility: "Core business concepts, invariants, and behavior"
    may_depend_on: [shared]
    must_not_depend_on: [client, server, application, adapters, contracts]

  contracts:
    path: "src/contracts/**"
    responsibility: "Stable data shapes crossing boundaries"
    may_depend_on: [shared]
    must_not_depend_on: [client, server, application, domain, adapters]

  application:
    path: "src/application/**"
    responsibility: "Use cases and orchestration"
    may_depend_on: [domain, contracts, shared]
    must_not_depend_on: [client, server, adapters]

  adapters:
    path: "src/adapters/**"
    responsibility: "External systems, DB, APIs, framework, tools"
    may_depend_on: [application, domain, contracts, shared]
    must_not_depend_on: [client]

  shared:
    path: "src/shared/**"
    responsibility: "Small primitives and utilities"
    may_depend_on: []
    must_not_depend_on: [client, server, application, domain, contracts, adapters]
```

Adjust module names to the actual repo.

---

## 11. Minimal Workflow

### First-time setup

```text
1. Install/wire CodeGraph.
2. Initialize the project once.
3. Create /architecture and the .claude/agents defs (surveyor, architect, builder, inspector).
4. Run Surveyor once.
5. Create architecture.md, boundaries.yaml, domain-model.md, data-contracts.md, and current.mmd.
```

### Every feature

```text
1. User gives feature request.
2. Architect reads intended architecture docs.
3. Architect asks one targeted CodeGraph query about the affected area.
4. Architect reconciles observed architecture with intended architecture.
5. If ALIGNED, continue.
6. If DOC_DRIFT_ACCEPTED, update docs in the patch.
7. If CODE_DRIFT_HARMFUL, propose a refactor/reconciliation patch before feature work.
8. If UNCLEAR_DRIFT, ask human.
9. Architect writes architecture patch.
10. Human approves or edits patch.
11. Builder implements only the patch.
12. Run tests.
13. Inspector checks changed files/symbols with one targeted CodeGraph query.
14. If accepted, update architecture docs and state.yaml.
15. Commit code and architecture artifacts together.
```

---

## 12. MVP Definition of Done

The MVP is working if it can:

```text
1. use CodeGraph as the source of truth for observed architecture
2. avoid repo-wide exploration
3. compare observed architecture with intended architecture docs
4. classify drift as accepted, harmful, or unclear
5. produce an architecture patch before coding
6. constrain coding to approved files and dependencies
7. preserve or intentionally evolve dependency structure
8. preserve or intentionally evolve domain classes
9. preserve or intentionally evolve data contract classes
10. reject raw boundary dictionaries and duplicated contracts
11. reject module-level business functions for domain behavior
12. validate changed dependency edges after coding
13. update intended architecture docs only when the change is accepted
14. keep architecture memory compact
```

---

## 13. Strongest Rule

Every feature must reconcile and preserve or intentionally evolve these three layers:

```text
1. dependency structure
2. domain model
3. data contracts
```

CodeGraph tells agents what exists.
Architecture docs tell agents what should remain true.
No silent architecture drift.
