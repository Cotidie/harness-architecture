# Data Contracts

Contract classes are the stable payload shapes that cross boundaries. They live
in `src/contracts/` and must not contain business logic (design Rule 6 and 7).

Per-contract definitions (names, fields, types, the boundary each crosses) live
in `contracts.yaml` as structured data, diffed against the code by
`scripts/intended_diff.py`. This file states the intended **rules** only.

## Intended rules

- Any data crossing a boundary (module, API, socket, queue, file, service,
  process, external tool) uses a dedicated contract class, never a raw dict or
  list.
- The intended flow is: `external payload -> contract class -> application
  layer -> domain class`.
- Contracts hold no business logic and are consumed at the application
  boundary, not imported inside domain policy (that would be a forbidden
  `domain -> contracts` edge).
- Contract lifecycle changes (create, expand, merge, split, rename, version)
  happen only through an approved architecture patch.

## Raw-payload risks

None observed yet. Watch for raw dict/list crossing a boundary once real code
lands.
