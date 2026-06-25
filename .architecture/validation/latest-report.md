# Validation Report: `--format json` output for the boundaries linter CLI

Patch: `.architecture/patches/2026-06-25-format-json.md`
Feature slug: format-json
Commit validated: 4f623d054dcaba82cddb632e25f0fc75110dcdf5
Validation time: 2026-06-25T08:42:34Z

## Decision: ACCEPT

Gate 2 conforms and the full design check list holds (Gate 1 passed mechanically upstream).

## Gate 1 - boundary edges + tests (run by orchestrator, PASSED)

- Tests: PASS. `python -m unittest discover -s tests` ran 70 tests, OK.
- Self-check: PASS. `python -m src.adapters.boundaries.cli src .architecture/boundaries.yaml`
  exit 0, zero violations.
- Scope: PASS. Changed files are exactly the 4 patch-allowed files:
  `src/adapters/boundaries/cli.py`, `src/adapters/boundaries/violation_reporter.py`,
  `tests/test_integration.py`, new `tests/test_violation_reporter.py`. No out-of-scope edit.

## Gate 2 - seam-signature conformance

One `codegraph_explore` query over the declared seams. Each implemented signature compared to the
patch's `## Seam signatures (Inspector gate 2)` block:

- `BoundaryViolation(source_module: str, target_module: str, rule_kind: str, file_path: str, line: int)`:
  MATCH (unchanged; contract file not edited, not in patch scope).
- `format_violation(violation: BoundaryViolation) -> str` (violation_reporter.py:10): MATCH (unchanged).
- `format_report(violations: Sequence[BoundaryViolation]) -> str` (violation_reporter.py:30): MATCH (unchanged).
- `format_report_json(violations: Sequence[BoundaryViolation]) -> str` (violation_reporter.py:40):
  MATCH (NEW; signature identical to declared, sibling to `format_report`, same input type).
- `run(target_dir: str, boundaries_file: str, output_format: str = "text") -> int` (cli.py:28):
  MATCH (defaulted `output_format` added exactly as declared; exit-code logic and the
  `matched_file_count == 0` could-not-run guard preserved).
- `main(argv: Sequence[str]) -> int` (cli.py:49): MATCH (signature unchanged; internal parsing moved
  to argparse with two positionals plus `--format {text,json}` default `text`; misuse caught via
  `SystemExit` maps to exit 2).

No seam renamed, removed, or signature-changed inside or outside the patch scope. No interface drift.

## Full check list

- Observed dependencies match the patch: PASS. Only stdlib `json` and `dataclasses` imports added,
  internal to `adapters`, crossing no module boundary.
- No forbidden / unapproved edge, no new cycle: PASS (self-check clean).
- No public interface drift outside the patch: PASS (all six seams match).
- No raw boundary payload: PASS. The JSON output (`dataclasses.asdict(v)` -> `json.dumps`) serializes
  the existing `BoundaryViolation` contract one-to-one over the same reporter -> stdout seam the text
  report already crosses; it is not a new cross-module contract.
- No duplicated contract class; contract change approved: PASS. `BoundaryViolation` unchanged (no
  field, type, or `rule_kind` value added); no new contract introduced.
- Business logic in a domain class: PASS / N/A. Output serialization is presentation and stays in the
  `adapters` reporter, consistent with the existing `format_report`. No module-level business logic.
- Required tests pass: PASS (70 tests; new `tests/test_violation_reporter.py` covers the formatters).
- Doc update: none deferred. No intended doc requires a change.

## CodeGraph query used (count: 1)

`BoundaryViolation format_report format_violation format_report_json run main argparse --format`

## Drift / violations found

None.
</content>
