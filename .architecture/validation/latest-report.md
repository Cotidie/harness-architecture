# Validation Report

Patch: `.architecture/patches/2026-06-25-may-only-depend-on.md`
Commit under validation: `9289b056beb285f595ff8d4a44b256a1dfc923d0`
Validation time: 2026-06-24T18:33:22Z

## Decision: ACCEPT

Both gates pass and the full check list holds.

## Gate 1 - boundary edges + tests

- Tests: PASS. `python -m unittest discover -s tests` ran 52 tests, OK.
- Self-check: PASS. `python -m src.adapters.boundaries.cli src .architecture/boundaries.yaml`
  reported "No boundary violations found." (exit 0). (The sample/ fixture line is the
  by-design fixture, not src/.)
- Scope: PASS. Every changed source/test/doc file is in the patch's "Files allowed to edit":
  `src/contracts/boundaries/module_rule.py`, `src/domain/boundaries/boundary_rule_set.py`,
  `src/application/boundaries/lint_boundaries.py`,
  `src/adapters/boundaries/boundaries_config_loader.py`, `.architecture/data-contracts.md`,
  `tests/test_boundary_rule_set.py`, `tests/test_contracts.py`, `tests/test_integration.py`.
  The patch file itself is the approved patch (not drift).

## Gate 2 - seam-signature conformance

One `codegraph_explore` query over the declared seams. Each compared to the patch:

- `ModuleRule(name, path_glob, may_depend_on, must_not_depend_on, may_only_depend_on)`: MATCH.
  New field is `Tuple[str, ...]` with `field(default_factory=tuple)`, matching the declared
  optional empty-tuple default.
- `BoundaryRuleSet.from_rules(rules: Iterable[Mapping[str, object]]) -> BoundaryRuleSet`: MATCH.
  Signature unchanged; reads the new optional key via `raw.get("may_only_depend_on", ()) or ()`.
- `BoundaryRuleSet.check(source_module: Optional[str], target_module: Optional[str], file_path: str, line: int) -> List[BoundaryDecision]`:
  MATCH. Signature unchanged; gains the allowlist branch (target known and absent from a
  present, non-empty allowlist) emitting `rule_kind="may_only_depend_on"`.
- `BoundaryDecision(source_module: str, target_module: str, rule_kind: str, file_path: str, line: int)`:
  MATCH. Unchanged; `rule_kind` is a free string now also carrying `"may_only_depend_on"`.

No seam renamed, removed, or signature-changed. No interface drift.

## Full check list

- Observed dependencies match the patch: PASS (no new edges).
- No forbidden / unapproved edge, no new cycle: PASS (self-check clean; domain still
  imports only stdlib, application maps the new field into a plain dict for `from_rules`).
- No public interface drift outside the patch: PASS.
- No raw boundary payload: PASS. `ModuleRule` carries the new field across the YAML-load
  boundary; application maps to a plain dict only as a domain input (not across a boundary).
- No duplicated contract class; contract change approved: PASS. One optional field added to
  `ModuleRule`; `rule_kind` value-space expansion, both authorized in patch sections 8 and 11.
- Business logic in a domain class: PASS. Allowlist decision lives in `BoundaryRuleSet.check`,
  not a module-level function.
- Required tests pass: PASS.
- Doc update: data-contracts.md update (new field + expanded `rule_kind` value set) is already
  included in this commit, so no doc update is deferred.

## CodeGraph query used (count: 1)

`ModuleRule contract fields, BoundaryRuleSet.from_rules, BoundaryRuleSet.check, BoundaryDecision dataclass signatures`
