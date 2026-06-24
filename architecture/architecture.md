# Intended Architecture

This document captures the INTENDED architecture (design memory). CodeGraph is
the source of truth for what the code currently contains. See `graph-notes.md`
for snapshot observations and any observed-vs-intended drift.

Status: this repository has no settled source code yet. The module map below is
the design's generic placeholder layout. The real stack and module names are
locked in iteration 2 when the boundaries-linter is built.

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

- Placeholder layout may not match the real stack chosen in iteration 2; expect
  this map to be refined then.
- No source code or tests exist yet, so boundary enforcement is unproven until
  the first real module lands.
