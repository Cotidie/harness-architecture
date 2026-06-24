# Architecture Patch: Boundaries Linter Hardening (iteration 3 bugfixes)

Date: 2026-06-25
Feature slug: linter-hardening

## 1. Feature request

User testing of iteration 3 found four issues in the existing boundaries linter
under `src/`. Harden the linter without breaking its current passing behavior.

1. HIGH (false negative): a nonexistent target dir, an empty tree, or a target
   whose paths match no module glob all print "No boundary violations found."
   and exit 0. A wrong cwd or an absolute target path silently lints nothing and
   reports success. The Inspector (iteration 4) will use this as a CI gate, so a
   silent pass on an unchecked tree is dangerous.
2. MEDIUM: bad config (missing file, empty or malformed YAML, missing `modules`,
   missing `path`) dumps a full Python traceback instead of a clean error.
3. MEDIUM: a target `.py` file with a syntax error raises an uncaught
   `SyntaxError` and aborts the whole lint.
4. LOW: config/runtime errors and violations both exit 1, so a caller cannot
   distinguish "failed to run" from "violations found". Arg-count errors already
   exit 2.

Desired behavior (scope, not implementation):
- Graceful errors: catch `FileNotFoundError` / `OSError` / `BoundariesConfigError`
  / `yaml.YAMLError`, print `error: <message>` to stderr, exit 2.
- Validate the target directory exists; if zero files match any module, warn or
  error rather than reporting clean (kills the false negative).
- Catch per-file `SyntaxError` in the scanner: emit a "could not parse" finding
  and continue, do not abort.
- Exit codes: 0 = clean, 1 = violations found, 2 = error / could-not-run.

## 2. Observed architecture (from CodeGraph)

Affected area: the linter's CLI / loader / scanner under `src/adapters/boundaries/`.

Modules and edges (current, as indexed):
- `src/adapters/boundaries/cli.py` : `main(argv)` -> `run(target, file)`.
  `run` wires `load_module_rules` (loader) + `LintBoundaries` (application) +
  `scan_imports` (scanner) + `format_report` (reporter). `run` returns
  `1 if violations else 0`; `main` returns 2 only on bad arg count.
- `src/adapters/boundaries/boundaries_config_loader.py` :
  `load_module_rules(path)` opens the YAML, validates structure, and raises
  `BoundariesConfigError` for bad structure. The bare `open(...)` and
  `yaml.safe_load(...)` propagate `FileNotFoundError` / `yaml.YAMLError`
  uncaught. Only module that imports PyYAML.
- `src/adapters/boundaries/python_import_scanner.py` :
  `scan_imports(target_dir, rule_set)` walks the tree with `os.walk`, calls
  `ast.parse(source, ...)` per `.py` file (uncaught `SyntaxError`), and emits
  `ImportEdge` contracts. Empty / nonmatching trees simply yield zero edges.
- `src/adapters/boundaries/violation_reporter.py` : `format_report(violations)`
  returns "No boundary violations found." for an empty sequence.
- `src/application/boundaries/lint_boundaries.py` : `LintBoundaries` maps
  `ModuleRule` -> domain inputs, calls `BoundaryRuleSet`, maps decisions back to
  `BoundaryViolation`. Depends only on domain + contracts.
- `src/domain/boundaries/boundary_rule_set.py` : `BoundaryRuleSet`
  (`from_rules`, `module_for_path`, `check`). No contract imports. Pure domain.

Contracts in play: `ImportEdge`, `BoundaryViolation`, `ModuleRule` (all frozen
dataclasses under `src/contracts/boundaries/`, no behavior).

Observed-vs-intended: layering is exactly as intended (dependencies point
inward; domain free of contracts; adapters do the IO; data crosses boundaries as
contracts). The four bugs are robustness gaps inside the adapters, not boundary
violations.

## 3. Intended architecture (from docs)

- `.architecture/architecture.md` module map:
  `shared <- domain`, `shared <- contracts`,
  `application -> {domain, contracts, shared}`,
  `adapters -> {application, domain, contracts, shared}`.
- `.architecture/boundaries.yaml`: `domain` and `contracts` must not depend on
  outer layers; `domain` must not depend on `contracts`.
- `.architecture/data-contracts.md`: any data crossing a boundary uses a
  dedicated contract class, never a raw dict / list. Contracts hold no behavior.
- `.architecture/domain-model.md`: business behavior lives in domain classes,
  not module-level functions.
- Known risk already documented: scanner resolves module-level absolute imports
  only. (Unchanged by this patch.)

## 4. Reconciliation decision

Label: **ALIGNED**.

Justification: the observed modules, edges, domain class, and contracts match the
intended architecture with zero drift. The CLI / loader / scanner are correctly
in `adapters`; the use case is in `application`; `BoundaryRuleSet` is pure domain
with no contract imports; boundary data already travels as `ImportEdge` /
`BoundaryViolation` / `ModuleRule` contracts. The four issues are missing error
handling and a missing emptiness check, fixable inside the existing layers
without moving any responsibility. Action: proceed with the feature in place; no
reconciliation refactor required.

## 5. Module changes

No modules created or removed. All changes stay inside existing adapter modules,
with one decision-helper added to the use case (see below).

| Module | Change | Reason |
|--------|--------|--------|
| `adapters/boundaries/cli.py` (modify) | Wrap `run` body in a try/except for `FileNotFoundError`, `OSError`, `BoundariesConfigError`, `yaml.YAMLError`; print `error: <message>` to stderr; return 2. Map outcomes to exit codes 0 / 1 / 2. Treat "scanned zero files" as an error (exit 2) per the false-negative fix. | Bugs 1, 2, 4. CLI is the composition root: it owns process exit code and stderr, so error-to-exit-code mapping belongs here, not in inner layers. |
| `adapters/boundaries/boundaries_config_loader.py` (modify) | Wrap the `open(...)` / `yaml.safe_load(...)` so OS and YAML parse failures surface as `BoundariesConfigError` (or are caught at the CLI); keep existing `BoundariesConfigError` structure messages. | Bug 2. Keeps all "config is bad" failures expressible as one clean error type the CLI can catch. |
| `adapters/boundaries/python_import_scanner.py` (modify) | Validate `target_dir` exists / is a directory (raise `FileNotFoundError` / `OSError` for the CLI to catch). Track a count of `.py` files actually attributed to a module. Wrap `ast.parse` per file in try/except `SyntaxError`: emit a parse-failure finding and continue. Return both the edges and the scanned-file count (or a small result object) so the CLI can detect "zero files matched". | Bugs 1, 3. Scanner owns the filesystem walk and parsing, so the existence check, the matched-file count, and per-file `SyntaxError` recovery belong here. |
| `application/boundaries/lint_boundaries.py` (modify) | Add a small decision so a parse-failure finding becomes a `BoundaryViolation`-shaped reported finding (see section 7/8). Continue mapping `ImportEdge` -> domain -> `BoundaryViolation` as today. | Bug 3. The "is a parse failure reportable / does it count toward exit 1" policy is application orchestration, not raw adapter logic. |
| `adapters/boundaries/violation_reporter.py` (modify, optional) | Render the parse-failure finding line. No change to the empty-list message (the CLI now guards the zero-files case before printing). | Bug 3 presentation. |

No new domain module: the existing fixes are IO robustness (adapters) and one
orchestration decision (application). The domain `BoundaryRuleSet` is unchanged.

## 6. Dependency changes

None. No new allowed or forbidden edges. All touched code keeps its current
layer:
- `cli.py` may import loader / scanner / reporter / application (adapters ->
  application, allowed) and `BoundariesConfigError` + `yaml` (it may reference
  the loader's error type; `yaml` import stays confined to the loader for the
  YAML parse, the CLI catches the exception type).
- scanner stays `adapters -> contracts, domain`.
- use case stays `application -> domain, contracts`.
No import is added that would create a forbidden edge.

## 7. Domain model changes

None. No new business behavior enters the domain. The "should a syntax error
count as a finding" choice is reporting / orchestration policy at the application
boundary, not a domain invariant, so `BoundaryRuleSet` is untouched. This
preserves the rule that the domain stays free of contracts and of IO concerns.

## 8. Data contract changes

The parse-failure finding crosses the scanner -> use case -> reporter boundary,
so per the no-raw-dict rule it must be a contract, not a tuple or dict.

Decision: **reuse `BoundaryViolation`** by introducing a distinct `rule_kind`
value (for example `"parse_error"`) and using `target_module`/`source_module`
fields for the affected file context. This adds no new field and no new class:
the existing frozen `BoundaryViolation` (file_path, line, source_module,
target_module, rule_kind) already carries everything a parse-failure line needs.

- Lifecycle action: **expand** the accepted value space of
  `BoundaryViolation.rule_kind` (add a `parse_error` kind). No structural change,
  no new contract class, no version bump of the dataclass shape.
- Reason: keeps the reporter and exit-code logic uniform (one findings stream),
  honors "no raw dict/list across a boundary", and avoids a near-duplicate
  contract. If a reviewer prefers an explicit separate `ParseFailure` contract
  under `src/contracts/boundaries/`, that is the alternative; flag it at approval.
- Register in `.architecture/data-contracts.md`: add `BoundaryViolation` (and
  `ImportEdge`, `ModuleRule`) to "Official data contracts" since they are now the
  real boundary shapes, and note the `rule_kind` value set including
  `parse_error`. (Doc currently says "None yet"; this records reality.)

The `target_dir does not exist` and `zero files matched` conditions do NOT cross
a boundary as data: they are CLI-level errors that go straight to stderr and
exit 2, so no contract is needed for them.

## 9. Files allowed to edit (bounded)

- `src/adapters/boundaries/cli.py` (error handling, exit-code mapping,
  zero-files guard).
- `src/adapters/boundaries/boundaries_config_loader.py` (wrap IO/YAML failures).
- `src/adapters/boundaries/python_import_scanner.py` (target-dir validation,
  matched-file count, per-file `SyntaxError` recovery).
- `src/application/boundaries/lint_boundaries.py` (parse-failure finding mapping).
- `src/adapters/boundaries/violation_reporter.py` (render parse-failure line).
- `.architecture/data-contracts.md` (register existing contracts +
  `parse_error` rule_kind).
- Tests under `tests/` (see section 10).

Do not edit: `src/domain/boundaries/boundary_rule_set.py`,
`src/contracts/boundaries/*.py` structure (only the documented `rule_kind` value
space expands, no field change), `.architecture/boundaries.yaml`,
`sample/boundaries.yaml`.

## 10. Tests required

Domain behavior:
- No new domain test (domain unchanged). Existing `BoundaryRuleSet` tests must
  still pass.

Contract validation:
- `tests/test_contracts.py`: a `BoundaryViolation` with `rule_kind="parse_error"`
  constructs and is frozen / equality-correct (no new field needed).

Boundary / integration (`tests/test_integration.py`):
- Nonexistent target dir -> exit 2, `error:` on stderr, not "No boundary
  violations found." (Bug 1).
- Empty tree or target matching no module glob -> exit 2 (or a loud warning per
  the chosen "warn or error" policy), never a silent clean exit 0 (Bug 1).
- Missing config file -> exit 2 + clean `error:` message, no traceback (Bug 2).
- Malformed YAML / missing `modules` / missing `path` -> exit 2 + clean
  `error:`, no traceback (Bug 2).
- Target containing one `.py` with a syntax error -> lint completes, emits a
  parse-failure finding, does not abort; other files still scanned (Bug 3).
- Exit-code matrix (Bug 4): clean tree -> 0; planted violation -> 1; any
  run failure -> 2; bad arg count -> 2 (already).

Regression (preserve existing passing behavior):
- `sample/` against `sample/boundaries.yaml` -> the planted violation + exit 1.
- `src/` self-check against `.architecture/boundaries.yaml` -> exit 0.

## 11. Risks

- Policy choice on "zero files matched": error (exit 2) is the safest CI gate and
  is what kills the false negative, but it could surprise a legitimately empty
  package. Recommend error-with-clear-message; downgrade to warn only if a real
  use case appears. Decide at approval.
- `parse_error` reused via `rule_kind` keeps one findings stream but slightly
  overloads `BoundaryViolation` semantics (a parse failure is not a dependency
  violation). Acceptable for now; revisit if findings diverge further.
- Whether a parse-failure finding should force exit 1 or exit 2: it is a
  could-not-fully-check condition. Recommend exit 1 (a reportable finding,
  consistent with "lint completed and found something") and keep exit 2 strictly
  for could-not-run. Confirm at approval.
- The documented import-resolution limitation (module-level absolute imports
  only) is unchanged and out of scope here.

## 12. Approval decisions (resolved by user, 2026-06-25)

- **Zero files matched a module glob:** ERROR, exit 2 (loud-fail CI gate). Kills the HIGH false negative.
- **Parse-failure exit code:** exit 1 (a reportable finding; lint completed). Exit 2 stays strictly for could-not-run.
- **Parse-failure shape:** reuse `BoundaryViolation` with `rule_kind="parse_error"` (no new class, no new field).

- [x] Approved (user, 2026-06-25). Authorizes Builder to implement this hardening patch.
