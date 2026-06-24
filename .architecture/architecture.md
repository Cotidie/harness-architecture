# Intended Architecture

This document captures the INTENDED architecture (design memory). CodeGraph is
the source of truth for what the code currently contains. See `graph-notes.md`
for snapshot observations and any observed-vs-intended drift.

Status: the stack is Python and the first real code has landed (the boundaries
linter under `src/`, iteration 3). The module map below is now the real intended
layout, not a placeholder.

## Intended module map

The repository will follow a layered dependency structure under `src/`:

```text
shared      -> (no deps)
domain      -> shared
contracts   -> shared
application -> domain, contracts, shared
adapters    -> application, domain, contracts, shared
```

| Module        | Path                 | Responsibility                                |
|---------------|----------------------|-----------------------------------------------|
| `domain`      | `src/domain/**`      | Core business concepts, invariants, behavior  |
| `contracts`   | `src/contracts/**`   | Stable data shapes crossing boundaries        |
| `application` | `src/application/**` | Use cases and orchestration                   |
| `adapters`    | `src/adapters/**`    | External systems: DB, APIs, framework, tools  |
| `shared`      | `src/shared/**`      | Small primitives and utilities                |

## Key boundaries

- Dependencies point inward toward the domain. `domain` and `contracts` are the
  innermost layers and must stay free of outer-layer imports.
- `domain` must not depend on `contracts`. External payloads are mapped to
  domain objects through the application layer, not by the domain importing DTOs.
- Data crossing a boundary must use a dedicated contract class, never a raw
  dict or list.
- Business behavior lives in domain classes, not in module-level functions.

## Accepted tradeoffs

- The layout is defined up front but mostly unmaterialized; modules appear as
  real code lands. This is accepted: the docs are intended architecture, not a
  mirror of current code.
- `shared` is defined in the design but not yet needed.

## Known risks

- Import resolution in the linter handles module-level absolute imports only;
  relative and function-local imports are skipped (documented limitation).
- The intended boundaries are now enforced by the linter's own self-check
  (`src/` against this `boundaries.yaml`), which passes with zero violations.
