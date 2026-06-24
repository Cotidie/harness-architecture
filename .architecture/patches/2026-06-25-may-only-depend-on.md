# Architecture Patch: `may_only_depend_on` allowlist rule

Date: 2026-06-25
Feature slug: may-only-depend-on

## 1. Feature request

Add a `may_only_depend_on` allowlist rule to the boundaries linter. A module may
declare `may_only_depend_on` (a list of module names). When present, any resolved
import from that module to a module NOT on the allowlist is a violation with
`rule_kind="may_only_depend_on"`. Imports that resolve to no known module (stdlib /
third party / external) are still ignored, as today. A module with no
`may_only_depend_on` key is unaffected (the rule is opt-in). The existing
`must_not_depend_on` behavior is unchanged.

## 2. Observed architecture (from CodeGraph)

Affected slice of the boundaries linter (one query):

- Contract `ModuleRule` (`src/contracts/boundaries/module_rule.py:11`): frozen
  dataclass, fields `name`, `path_glob`, `may_depend_on`, `must_not_depend_on`.
  Callers: `LintBoundaries.build_rule_set`, `load_module_rules`.
- Domain `BoundaryRuleSet` (`src/domain/boundaries/boundary_rule_set.py:50`):
  frozen value object built from plain mappings via `from_rules`. `_ModuleEntry`
  holds `name`, `path_glob`, `may_depend_on`, `must_not_depend_on` (tuples).
  `check(...)` returns `List[BoundaryDecision]`; today it flags only when the
  target is in the source's `must_not_depend_on`, ignoring unknown/self pairs.
  Module imports only stdlib (no `contracts` import: intended edge preserved).
- Application `LintBoundaries` (`src/application/boundaries/lint_boundaries.py:22`):
  `build_rule_set` maps `ModuleRule` contracts into plain dict rows
  (`name`, `path_glob`, `may_depend_on`, `must_not_depend_on`) and calls
  `BoundaryRuleSet.from_rules`. `run` maps each `BoundaryDecision` back onto a
  `BoundaryViolation` contract.
- Adapter loader `load_module_rules`
  (`src/adapters/boundaries/boundaries_config_loader.py:20`): the only PyYAML
  importer; reads `modules.<name>.{path, may_depend_on, must_not_depend_on}` and
  builds `ModuleRule` instances.
- `BoundaryDecision.rule_kind` is a free string; `BoundaryViolation.rule_kind`
  already accepts an expandable value set (`must_not_depend_on`, `parse_error`).

The data flow matches intended: `yaml -> ModuleRule (contract) -> application maps
to plain dict -> BoundaryRuleSet (domain) -> BoundaryDecision -> BoundaryViolation`.

## 3. Intended architecture (from docs)

- Layered, dependencies inward: `domain` and `contracts` innermost; `domain`
  must NOT import `contracts`; payloads map to domain inputs in the application
  layer (architecture.md, domain-model.md).
- Data crossing a boundary uses a dedicated contract class, never a raw dict/list
  (data-contracts.md). `ModuleRule` is the registered YAML-load contract.
- Business behavior lives in domain classes, not module-level functions
  (domain-model.md). The allowlist decision is business logic, so it belongs in
  `BoundaryRuleSet`, not a free function.
- `BoundaryViolation.rule_kind` is an expandable value set already (precedent:
  `parse_error`); adding `may_only_depend_on` follows the same pattern with no
  new field and no new class.

## 4. Reconciliation decision

Label: **ALIGNED**.

Justification: observed contract shape, domain ownership of the check, application
mapping, and the expandable `rule_kind` value set all match the intended docs for
the area this feature touches; the change extends existing seams without crossing
any boundary, so no reconciliation is needed before the feature.

Unrelated observed drift: none in the affected slice.

## 5. Module changes

None. No module is created, moved, or removed. The change is confined to existing
modules (`contracts`, `domain`, `application`, `adapters`) and respects current
boundaries.

## 6. Dependency changes

None. No new allowed or forbidden edge. The existing edges are reused:
`adapters -> contracts`, `application -> {contracts, domain}`, and `domain`
stays free of `contracts` (the application layer still maps the new contract
field into plain dict inputs for `from_rules`).

## 7. Domain model changes

Expand the existing `BoundaryRuleSet` value object (and its private
`_ModuleEntry`) with an opt-in `may_only_depend_on` allowlist. No new domain
class, no module-level function. `from_rules` reads the new optional key from the
plain input rows; `check` adds the allowlist branch (target known and not on a
present, non-empty allowlist) emitting `rule_kind="may_only_depend_on"`. Unknown
targets and self-references stay ignored; absence of the key leaves behavior
unchanged. The public `check` and `from_rules` signatures are unchanged in shape;
only the internal entry gains a field and `check` gains a branch.

Seam signatures (public domain entry points; `_ModuleEntry` is private and shown
for reference only):

- `BoundaryRuleSet.from_rules(rules: Iterable[Mapping[str, object]]) -> BoundaryRuleSet`
- `BoundaryRuleSet.check(source_module: Optional[str], target_module: Optional[str], file_path: str, line: int) -> List[BoundaryDecision]`
- `BoundaryDecision(source_module: str, target_module: str, rule_kind: str, file_path: str, line: int)` (unchanged; `rule_kind` now also takes `"may_only_depend_on"`)

## 8. Data contract changes

Expand the `ModuleRule` contract with one optional field `may_only_depend_on:
Tuple[str, ...]` (default empty tuple), mirroring `may_depend_on` /
`must_not_depend_on`. No new contract class; no merge/split/rename. The
`BoundaryViolation` contract is unchanged: its `rule_kind` value set expands to
include `"may_only_depend_on"` (a value-space expansion, same precedent as
`parse_error`), adding no field and no class.

Changed contract signature:

- `ModuleRule(name: str, path_glob: str, may_depend_on: Tuple[str, ...], must_not_depend_on: Tuple[str, ...], may_only_depend_on: Tuple[str, ...])`

## 9. Files allowed to edit

- `src/contracts/boundaries/module_rule.py` (add `may_only_depend_on` field).
- `src/domain/boundaries/boundary_rule_set.py` (add field to `_ModuleEntry`,
  read key in `from_rules`, add allowlist branch in `check`).
- `src/application/boundaries/lint_boundaries.py` (map new contract field into
  the plain dict row in `build_rule_set`).
- `src/adapters/boundaries/boundaries_config_loader.py` (parse the new
  `may_only_depend_on` key into `ModuleRule`).
- `.architecture/data-contracts.md` (register the new field and the expanded
  `rule_kind` value set).
- Test files (section 10): `tests/test_boundary_rule_set.py`,
  `tests/test_contracts.py`, `tests/test_integration.py`.

## 10. Tests required

- Domain behavior (`tests/test_boundary_rule_set.py`):
  - import to a module ON the allowlist: no violation;
  - import to a known module NOT on the allowlist: one `BoundaryDecision` with
    `rule_kind="may_only_depend_on"`;
  - import resolving to an unknown module (stdlib / third party): ignored;
  - self-reference: ignored;
  - module with no `may_only_depend_on` key: unaffected;
  - empty `may_only_depend_on` list present: treated as opt-out (unaffected),
    decide and document the chosen semantics in the test;
  - `must_not_depend_on` behavior unchanged (regression).
- Contract validation (`tests/test_contracts.py`): `ModuleRule` constructs with
  and without `may_only_depend_on`; default is an empty tuple; instance stays
  frozen.
- Boundary / integration (`tests/test_integration.py`): a `boundaries.yaml`
  fixture with a `may_only_depend_on` module produces a `BoundaryViolation`
  carrying `rule_kind="may_only_depend_on"` end to end through
  `load_module_rules -> LintBoundaries.run`.

## 11. Risks

- Semantics of an empty allowlist (`may_only_depend_on: []`) must be pinned: this
  patch treats an empty/absent list as opt-out (rule inactive) so the rule stays
  strictly opt-in; the test suite must lock this in.
- A module declaring both `must_not_depend_on` and `may_only_depend_on` could
  produce two findings for the same edge; that is acceptable (two distinct
  `rule_kind` values), but tests should document it.
- The contract field defaulting to an empty tuple keeps existing YAML and callers
  working; the loader must coerce a missing key to `()` to avoid `None`.

- [x] Approved (user, 2026-06-25). Authorizes iteration 4 dogfood (Builder) to implement this patch.

## Seam signatures (Inspector gate 2)

- `ModuleRule(name: str, path_glob: str, may_depend_on: Tuple[str, ...], must_not_depend_on: Tuple[str, ...], may_only_depend_on: Tuple[str, ...])`
- `BoundaryRuleSet.from_rules(rules: Iterable[Mapping[str, object]]) -> BoundaryRuleSet`
- `BoundaryRuleSet.check(source_module: Optional[str], target_module: Optional[str], file_path: str, line: int) -> List[BoundaryDecision]`
- `BoundaryDecision(source_module: str, target_module: str, rule_kind: str, file_path: str, line: int)`
