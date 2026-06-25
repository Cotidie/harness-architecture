# Intended Domain Model

Domain classes are first-class. Business behavior belongs here, not in
module-level functions. CodeGraph is the source of truth for what currently
exists; this file records what should be preserved.

Per-class definitions (key domain classes, their responsibilities, invariants,
and public method signatures) live in `domain-model.yaml` as structured data,
diffed against the code by `scripts/intended_diff.py`. This file states the
intended **rules** only. The curated key domain class is `BoundaryRuleSet` (the
boundary-policy object); new business behavior must take the shape of a domain
class or method under `src/domain/`, not a module-level function.

## Invariants to preserve

- Domain objects own their invariants (prefer frozen value objects with
  factory methods so invalid states cannot be constructed).
- Business rules, state transitions, and validation policy live inside domain
  classes, never in the application or adapter layers.

## Rules (design Rule 5 and 7)

- Prefer a policy object (for example `RouteRiskPolicy.evaluate(...)`) over a
  free function (for example `calculate_route_risk(...)`).
- Keep domain classes (`src/domain/`) separate from data contract classes
  (`src/contracts/`). The domain must not import contracts; the application
  layer maps payloads to domain inputs.

## Refactor candidates

None yet. Populated by reconciliation when real code drifts from these rules.
