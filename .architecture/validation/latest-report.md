# Validation report: `--quiet` flag for the boundaries linter CLI

Patch: `.architecture/patches/2026-06-25-quiet-flag.md`
Feature slug: quiet-flag
Changed files: `src/adapters/boundaries/cli.py`, `tests/test_integration.py`

## Decision: ACCEPT

Gate 2 conforms and the full design check list holds (Gate 1 passed mechanically upstream).

## Gate 1 - boundary edges + tests (run upstream by orchestrator: PASS)

- Tests: PASS. `python -m unittest discover -s tests` -> 76 tests OK.
- Self-check: PASS. `python -m src.adapters.boundaries.cli src .architecture/boundaries.yaml`
  exit 0, zero violations.
- Scope: PASS. Changed files are exactly the 2 patch-allowed files
  (`src/adapters/boundaries/cli.py`, `tests/test_integration.py`). No out-of-scope edit.

Not re-run here.

## Gate 2 - seam-signature conformance

One `codegraph_explore` query over the declared seams (`run`, `main`). Each implemented signature
compared to the patch's `## Seam signatures (Inspector gate 2)` block:

- `run`: declared proposed
  `run(target_dir: str, boundaries_file: str, output_format: str = "text", quiet: bool = False) -> int`.
  Implemented at `src/adapters/boundaries/cli.py:28-33` is exactly that signature. MATCH.
- `main`: declared `main(argv: Sequence[str]) -> int` unchanged, adding a `--quiet` argparse flag
  (`dest="quiet"`, `action="store_true"`, default `False`) threaded into `run`. Implemented at
  `cli.py:55` keeps the signature; the flag is added at `cli.py:67-72` with exactly those
  attributes and is threaded into `run` at `cli.py:85`. MATCH.

No seam renamed, removed, or signature-changed inside or outside the patch scope. No interface drift.

## Full check list

- Suppression placement: the clean-run guard lives in `run` (`cli.py:50-51`,
  `if not (quiet and not violations): print(formatter(violations))`), not in the reporter, as the
  patch required. argparse, stdout, and exit-code ownership stay in the `adapters` composition root. PASS.
- Observed dependencies match the patch: PASS. No import changes in `cli.py`; the
  `adapters` -> `application` edge is allowed by `boundaries.yaml`.
- No forbidden / unapproved edge, no new cycle: PASS (self-check clean upstream; no new imports).
- No public interface drift outside the patch: PASS. `LintBoundaries.run` / `build_rule_set`,
  `BoundaryRuleSet`, `BoundaryDecision` signatures unchanged.
- No raw boundary payload: PASS. The application layer still maps domain `BoundaryDecision` onto the
  `BoundaryViolation` contract; no dict/list crosses a boundary. `--quiet` is a process-local
  presentation toggle.
- No duplicated contract class; contract change approved: PASS. No contract created, expanded,
  merged, split, renamed, or versioned.
- Business logic in a domain class: PASS / N/A. The `quiet` guard is adapter-level presentation
  logic, not domain behavior; no module-level business logic added.
- Required tests pass: PASS (76 tests; gate-1 upstream).
- Doc update: none deferred. No intended doc requires a change.

## CodeGraph query used (count: 1)

`run main cli.py boundaries linter run(target_dir, boundaries_file, output_format, quiet) argparse --quiet flag print clean-run`

## Drift / violations found

None.

## Next action

`none` (ACCEPT). The orchestrator owns the validated-commit bump in `state.yaml`; not touched here.
