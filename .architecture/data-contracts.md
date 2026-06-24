# Data Contracts

Contract classes are the stable payload shapes that cross boundaries. They live
in `src/contracts/` and must not contain business logic (design Rule 6 and 7).

Status: official contracts now exist for the boundaries linter and are
registered below. This file states the intended rules; further contracts are
registered as real boundaries appear.

## Official data contracts

The boundaries linter's payload shapes (frozen dataclasses under
`src/contracts/boundaries/`, no behavior):

- `ModuleRule` (`module_rule.py`): one module entry loaded from
  `boundaries.yaml`. Crosses the YAML-load boundary (loader -> application).
  Fields: `name`, `path_glob`, `may_depend_on`, `must_not_depend_on`.
- `ImportEdge` (`import_edge.py`): one resolved module-level import. Crosses the
  scanner -> application boundary. Fields: `source_module`, `imported_module`,
  `file_path`, `line`.
- `BoundaryViolation` (`boundary_violation.py`): one reported finding. Crosses
  the application -> reporter boundary, and (for parse failures) the scanner ->
  application -> reporter boundary. Fields: `source_module`, `target_module`,
  `rule_kind`, `file_path`, `line`.
  - `rule_kind` value set: `"must_not_depend_on"` (a dependency-rule violation)
    and `"parse_error"` (a file that could not be parsed; the affected file is
    in `file_path`/`line`, and `source_module`/`target_module` carry its module
    context). The `parse_error` value expands the accepted value space of the
    existing contract; it adds no new field and no new class.

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
