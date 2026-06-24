# Architecture Patch: Boundaries Linter

Date: 2026-06-25
Status: Proposed (awaiting approval)

## 1. Feature request

Add a boundaries linter. It loads a `boundaries.yaml` (module path globs plus
`may_depend_on` / `must_not_depend_on`), scans a target Python source tree,
resolves each module's imports to modules, and reports every import that
violates a `must_not_depend_on` rule, exiting non-zero when any violation
exists. The first lint target is the `sample/` fixture with
`sample/boundaries.yaml`. Stack is Python, stdlib only where possible (for
example `ast` for import parsing).

## 2. Observed architecture from CodeGraph

One `codegraph_explore` query was run against the affected area (the `sample/`
fixture and where linter code would attach).

Affected modules and edges (the lint target, `sample/`):

- `sample/contracts/route_dto.py` -> `RouteRequestDTO` (frozen dataclass, no
  imports of other sample modules).
- `sample/domain/route_risk.py` -> `RouteRisk` (frozen value object with
  `from_score` factory; imports only `dataclasses`).
- `sample/domain/route_risk_policy.py` -> `RouteRiskPolicy.evaluate(...)`;
  imports `sample.domain.route_risk` AND `sample.contracts.route_dto`.
- `sample/application/plan_route.py` -> `PlanRouteUseCase`; imports
  `sample.contracts.route_dto`, `sample.domain.route_risk`,
  `sample.domain.route_risk_policy` (all allowed for `application`).
- `sample/adapters/route_repository.py` -> `RouteRepository`; imports
  `sample.application.plan_route`, `sample.domain.route_risk` (allowed for
  `adapters`).

Domain classes observed: `RouteRisk`, `RouteRiskPolicy` (under
`sample/domain/`). Contract classes observed: `RouteRequestDTO` (under
`sample/contracts/`).

Planted drift acknowledged: `sample/domain/route_risk_policy.py` line 9 imports
`RouteRequestDTO` from `sample.contracts.route_dto`. Under
`sample/boundaries.yaml`, `domain.must_not_depend_on` includes `contracts`, so
this is a real forbidden `domain -> contracts` edge. This is intentional fixture
drift, and it is exactly the violation the new linter must detect and report
(it is NOT to be fixed by this patch).

Real repo (`src/`): no source code exists yet. This is greenfield. The linter
itself is the first real code to land under `src/`.

## 3. Intended architecture from docs

From `.architecture/architecture.md`, `.architecture/boundaries.yaml`,
`.architecture/domain-model.md`, `.architecture/data-contracts.md`:

- Layered structure under `src/`:
  `shared` (no deps) <- `domain`, `contracts` (depend on `shared` only) <-
  `application` (domain, contracts, shared) <- `adapters` (application, domain,
  contracts, shared).
- `domain` must not depend on `contracts`; payloads map to domain inputs in the
  application layer.
- Data crossing a boundary uses a dedicated contract class, never a raw dict or
  list.
- Business behavior lives in domain classes (prefer a policy object such as
  `RouteRiskPolicy.evaluate(...)` over a module-level function), not in
  module-level functions.
- The linter is intended to live in the `adapters` layer: it is a tool that
  touches the filesystem (reads YAML, walks a source tree, parses files), and
  `adapters` is the layer for external systems and tools. The boundary-check
  business rule lives in `domain`; the contract shapes live in `contracts`; the
  `adapters` layer orchestrates IO and parsing and delegates the decision to the
  domain.

## 4. Reconciliation decision

Label: CODE_DRIFT_HARMFUL (scoped to the `sample/` fixture).

Justification: the observed `sample/domain/route_risk_policy.py -> contracts`
edge violates the intended `domain must_not_depend_on contracts` rule. It is a
harmful drift by design (the planted fixture). Action: do NOT change the
fixture. Build the linter so that, run against `sample/` with
`sample/boundaries.yaml`, it detects and reports this edge and exits non-zero.
The fixture violation is the linter's first acceptance test, not a refactor
target.

For the real `src/` tree the state is greenfield (ALIGNED by absence): no code
exists, so the new linter modules are the first to materialize the intended
layout, and they must themselves obey `.architecture/boundaries.yaml`.

## 5. Module changes (create / modify / remove)

Create (all under `src/`, matching the intended layout):

- `src/domain/boundaries/` (new domain area)
  - `boundary_rule_set.py` -> domain class holding the parsed rules and owning
    the violation-detection behavior. Reason: the boundary-check business rule
    must live in a domain class, not a module-level function.
- `src/contracts/boundaries/` (new contract area)
  - `module_rule.py` -> contract class for one module's rule (name, path glob,
    may/must-not lists). Reason: rule data crosses the YAML-load boundary.
  - `import_edge.py` -> contract class for a resolved import (source module,
    imported module, file, line). Reason: parsed-import data crosses the
    scanner boundary.
  - `boundary_violation.py` -> contract class for one reported violation
    (source module, target module, rule kind, file, line). Reason: violation
    data crosses back out to the reporter.
- `src/adapters/boundaries/` (new adapter area: tool + IO + parsing)
  - `boundaries_config_loader.py` -> loads and validates `boundaries.yaml`,
    builds `ModuleRule` contracts and the `BoundaryRuleSet` domain object.
  - `python_import_scanner.py` -> walks the target tree, uses `ast` to parse
    imports, maps files and imports to module names via the rule path globs,
    and emits `ImportEdge` contracts.
  - `violation_reporter.py` -> formats `BoundaryViolation` contracts for output.
  - `cli.py` -> entry point: wires loader + scanner + rule set + reporter, sets
    the process exit code (non-zero when any violation exists).
- `src/application/boundaries/`
  - `lint_boundaries.py` -> use case orchestrating loader -> scanner ->
    rule-set evaluation -> reporter. Reason: orchestration belongs in the
    application layer; it maps adapter-parsed contracts into the domain.

Modify: none.

Remove: none.

Note: `src/shared/` is not needed for this feature and is not created.

## 6. Dependency changes

Allowed edges introduced (all conform to `.architecture/boundaries.yaml`):

- `src/contracts/boundaries/*` -> (stdlib only; no inward sample/src deps).
- `src/domain/boundaries/boundary_rule_set.py` -> stdlib only. It must NOT
  import the new contracts (would create a forbidden `domain -> contracts`
  edge). It operates on plain domain inputs passed by the application layer.
- `src/application/boundaries/lint_boundaries.py` -> `src/domain/boundaries`,
  `src/contracts/boundaries` (allowed: application may depend on domain and
  contracts).
- `src/adapters/boundaries/*` -> `src/application/boundaries`,
  `src/domain/boundaries`, `src/contracts/boundaries` (allowed: adapters may
  depend on application, domain, contracts).

External dependency (amendment, iteration-3 decision):

- The linter takes one external dependency, **PyYAML**, to parse `boundaries.yaml`. It is
  imported ONLY in `src/adapters/boundaries/boundaries_config_loader.py`. External deps belong
  in the adapters layer, so this conforms to the intended boundaries. Tests use stdlib
  `unittest` (no test-framework dependency).

Forbidden edges to actively avoid while building:

- `src/domain/boundaries -> src/contracts/boundaries` (forbidden; the domain
  rule set must not import the contract classes). The application layer maps
  `ModuleRule` / `ImportEdge` contract data into the domain object's inputs.
- `src/domain/boundaries -> src/application` or `-> src/adapters` (forbidden).
- `src/contracts/boundaries -> src/domain` (forbidden).

The linter's own first run target is the `sample/` tree; the
`sample/domain -> sample/contracts` edge it detects is the planted fixture
violation, reported, not fixed.

## 7. Domain model changes

Add domain class `BoundaryRuleSet` under `src/domain/boundaries/`:

- Constructed from already-validated rule inputs (module name, compiled path
  glob, may-depend-on set, must-not-depend-on set) supplied by the application
  layer. Prefer a frozen value object with a factory method so invalid states
  cannot be constructed (per domain-model invariants).
- Owns the business behavior: `module_for_path(path)` (which module a file
  belongs to) and `check(import_edge_inputs) -> violations` (decide whether a
  resolved source-module -> target-module pair breaks a `must_not_depend_on`
  rule). This is the boundary-check logic and it lives in a domain
  class/method, never a module-level function.
- The domain class takes plain inputs (strings, sets, line numbers), not the
  contract classes, to preserve `domain must_not_depend_on contracts`.

## 8. Data contract changes

Register three new official contract classes under `src/contracts/boundaries/`
(frozen dataclasses, no business logic):

- `ModuleRule`: `name`, `path_glob`, `may_depend_on` (tuple), `must_not_depend_on`
  (tuple). Shape of one module entry loaded from `boundaries.yaml`.
- `ImportEdge`: `source_module`, `imported_module`, `file_path`, `line`. Shape of
  one resolved import emitted by the scanner.
- `BoundaryViolation`: `source_module`, `target_module`, `rule_kind`
  (`must_not_depend_on`), `file_path`, `line`. Shape of one reported violation.

Rationale: boundary data (rules, edges, violations) crosses module, file, and
tool boundaries, so each must be a dedicated contract class, never a raw dict or
list. Contracts hold no logic; the domain `BoundaryRuleSet` makes decisions and
the application layer maps between contracts and domain inputs.

## 9. Files allowed to edit (bounded list, Python under src/)

- `src/__init__.py` (create)
- `src/contracts/__init__.py` (create)
- `src/contracts/boundaries/__init__.py` (create)
- `src/contracts/boundaries/module_rule.py` (create)
- `src/contracts/boundaries/import_edge.py` (create)
- `src/contracts/boundaries/boundary_violation.py` (create)
- `src/domain/__init__.py` (create)
- `src/domain/boundaries/__init__.py` (create)
- `src/domain/boundaries/boundary_rule_set.py` (create)
- `src/application/__init__.py` (create)
- `src/application/boundaries/__init__.py` (create)
- `src/application/boundaries/lint_boundaries.py` (create)
- `src/adapters/__init__.py` (create)
- `src/adapters/boundaries/__init__.py` (create)
- `src/adapters/boundaries/boundaries_config_loader.py` (create)
- `src/adapters/boundaries/python_import_scanner.py` (create)
- `src/adapters/boundaries/violation_reporter.py` (create)
- `src/adapters/boundaries/cli.py` (create)
- Test files under `tests/` per section 10 (create)
- `requirements.txt` (create): pins PyYAML (amendment, iteration-3 dependency decision)

Out of scope (must NOT edit): everything under `sample/` (the fixture, including
the planted violation), and the `.architecture/` docs except this patch.

## 10. Tests required

Domain behavior:

- `BoundaryRuleSet.module_for_path` maps a sample file path to the correct
  module via path glob; returns no module for an unmatched path.
- `BoundaryRuleSet.check` flags a source -> target pair that is in
  `must_not_depend_on`, and does not flag an allowed pair.
- Frozen / factory invariants: invalid rule inputs cannot construct a rule set.

Contract validation:

- `ModuleRule`, `ImportEdge`, `BoundaryViolation` are frozen, hold the expected
  fields, contain no behavior, and reject construction with missing fields.

Boundary / integration:

- End-to-end: run the linter (loader + scanner + rule set + reporter) against
  the `sample/` tree with `sample/boundaries.yaml`. Assert it reports exactly
  the planted `sample.domain.route_risk_policy -> sample.contracts.route_dto`
  violation (correct file and line) and exits non-zero.
- Clean case: a tree with no `must_not_depend_on` violations reports nothing and
  exits zero.
- Self-check (architecture guard): running the linter on `src/` with
  `.architecture/boundaries.yaml` reports zero violations (the new code obeys
  its own intended boundaries, in particular no `domain -> contracts` edge).

## 11. Risks

- Import-to-module resolution: relative imports, `import a.b.c` vs
  `from a.b import c`, and conditional / function-local imports may be resolved
  imperfectly by `ast`. Scope to module-level absolute imports first; document
  the limitation.
- Path-glob to module mapping must be unambiguous; overlapping globs in a
  `boundaries.yaml` could assign a file to more than one module. Define a
  deterministic rule (for example most-specific glob wins) and test it.
- Self-check risk: it is easy to accidentally import a contract class inside the
  domain rule set. The section-10 self-check test guards against this.
- External imports (stdlib, third party) that map to no module must be ignored,
  not reported, to avoid false positives.

- [x] Approved (user, 2026-06-25). Authorizes iteration 3 (Builder) to implement this patch.

Amendment (2026-06-25, iteration 3): added the PyYAML external dependency (adapters loader
only) and `requirements.txt` to the allowed files. Tests use stdlib unittest. Approval stands.
