# Architecture Patch: `--format json` output for the boundaries linter CLI

Date: 2026-06-25
Feature slug: format-json

## 1. Feature request

Add a `--format json` output option to the boundaries linter CLI. The CLI should accept
`--format {text,json}` (default `text`, current behavior). With `--format json`, it prints the
violations as a JSON array to stdout instead of the human-readable text report. Exit codes stay
unchanged (0 clean, 1 findings, 2 could-not-run).

## 2. Observed architecture (from CodeGraph)

Affected modules and the current call flow:

- `main` (`src/adapters/boundaries/cli.py:42`) -> `run` (`cli.py:24`) -> `format_report`
  (`src/adapters/boundaries/violation_reporter.py:28`).
- `main` does manual positional-argument handling, not argparse: it requires exactly 2 args
  (`<target_dir> <boundaries_file>`), writes a usage string to stderr and returns 2 on misuse,
  and maps loader/scan/YAML errors to exit 2. `run` prints `format_report(...)` and returns
  `1 if violations else 0`.
- `format_report(violations: Sequence[BoundaryViolation]) -> str` builds the text report;
  `format_violation(violation: BoundaryViolation) -> str` renders one finding (including the
  `parse_error` kind). Neither has covering tests (CodeGraph blast radius flags this).
- Contract crossing the application -> reporter boundary: `BoundaryViolation` (frozen dataclass,
  `src/contracts/boundaries/boundary_violation.py`) with fields `source_module`,
  `target_module`, `rule_kind`, `file_path`, `line`. 10 callers; covered by `tests/test_contracts.py`.
- The CLI adapter lives in `adapters`, depends on `application` (`LintBoundaries`), the reporter,
  loader, and scanner (all `adapters`), and on the `contracts` shape indirectly. No domain logic
  lives in the CLI or the reporter.

## 3. Intended architecture (from docs)

- Layering (`architecture.md`, `boundaries.yaml`): `adapters` may depend on `application`,
  `domain`, `contracts`, `shared`. The CLI and reporter are correctly in `adapters`. No new edge
  is needed.
- Contracts (`data-contracts.md`): data crossing a boundary uses a dedicated contract class, never
  a raw dict/list. `BoundaryViolation` is the official contract for one finding; its `rule_kind`
  value set is `must_not_depend_on`, `may_only_depend_on`, `parse_error`.
- Domain model (`domain-model.md`): business behavior must be a domain class/method, not a
  module-level function. Output formatting is presentation, not business behavior, so it stays in
  the `adapters` reporter (consistent with the existing `format_report`).

## 4. Reconciliation decision

Label: **ALIGNED**.

Justification: the feature touches only the `adapters` CLI and reporter. Observed placement
(CLI and reporter in `adapters`, `BoundaryViolation` as the boundary contract) matches the intended
layered architecture, and the change introduces no new cross-module edge and no domain logic. The
only notable gap is that `format_report`/`format_violation` have no covering tests, which this
patch addresses (section 10) rather than treating as harmful drift.

Unrelated observed drift: none surfaced in the affected area.

## 5. Module changes

None. No module is created, moved, or removed. Both touched files stay in `adapters`.

## 6. Dependency changes

None. The CLI may add a stdlib `json` import (internal to `adapters`); this crosses no module
boundary. No allowed or forbidden edge changes.

## 7. Domain model changes

None. Output serialization is presentation in the `adapters` reporter, not domain behavior. No
domain class is created, expanded, or moved.

## 8. Data contract changes

None. `BoundaryViolation` is unchanged (no new field, no new class, no new `rule_kind` value). The
JSON output serializes the existing contract fields; the JSON array element shape mirrors the
contract one-to-one (`source_module`, `target_module`, `rule_kind`, `file_path`, `line`). The
JSON-to-stdout output is not a new cross-module contract: it is the same reporter -> stdout seam
that the text report already crosses, rendered in a second format.

Seam signatures for the touched entry points (`current -> proposed` / `unchanged` / `NEW`):

- `BoundaryViolation(source_module: str, target_module: str, rule_kind: str, file_path: str, line: int)`
  -> unchanged.
- `violation_reporter.format_report(violations: Sequence[BoundaryViolation]) -> str` -> unchanged
  (the text path keeps the current default behavior).
- `violation_reporter.format_violation(violation: BoundaryViolation) -> str` -> unchanged.
- `violation_reporter.format_report_json(violations: Sequence[BoundaryViolation]) -> str` -> NEW
  (returns a JSON array string of the violation objects; sibling to `format_report`, same input
  type, no behavior beyond serialization).
- `cli.run(target_dir: str, boundaries_file: str) -> int`
  -> `cli.run(target_dir: str, boundaries_file: str, output_format: str = "text") -> int`
  (selects `format_report` vs `format_report_json`; exit-code logic and the
  `matched_file_count == 0` could-not-run guard are unchanged).
- `cli.main(argv: Sequence[str]) -> int` -> unchanged signature; internal arg handling moves from
  manual positional parsing to argparse accepting two positionals plus
  `--format {text,json}` (default `text`). Misuse still returns 2; clean/findings/could-not-run
  exit codes (0/1/2) are unchanged.

## 9. Files allowed to edit

- `src/adapters/boundaries/violation_reporter.py` (add `format_report_json`).
- `src/adapters/boundaries/cli.py` (argparse with `--format`, thread `output_format` into `run`,
  select formatter).
- `tests/test_integration.py` (CLI `--format json` and default-text behavior, exit codes).
- New: `tests/test_violation_reporter.py` (unit tests for the reporter formatters).

## 10. Tests required

- Reporter (unit): `format_report_json` emits a JSON array; each element carries the five
  `BoundaryViolation` fields with correct values; empty input emits `[]`; a `parse_error` finding
  serializes with `rule_kind == "parse_error"`. Also pin existing `format_report` text output
  (currently untested per CodeGraph).
- CLI / integration: `--format json` prints valid parseable JSON to stdout and no text report;
  default (no flag) and `--format text` preserve current text output; an invalid `--format` value
  returns exit 2; exit codes stay 0 (clean), 1 (findings), 2 (could-not-run, e.g. zero matched
  files or loader error) across both formats.
- Boundary/integration: confirm no new cross-module import edge is introduced (the linter
  self-check over `src/` still passes with zero violations).

## 11. Risks

- argparse refactor of `main` could change misuse/exit-code behavior: pin exit 2 for bad/missing
  args and invalid `--format` with a test.
- JSON field order/shape could drift from the contract: assert the element keys equal the five
  `BoundaryViolation` fields so the JSON stays a faithful serialization.
- Low blast radius: `run`/`format_report` callers are internal to `cli.py`; the `run` signature
  gains a defaulted parameter, so existing callers stay source-compatible.

- [x] Approved (human, 2026-06-25)

## Seam signatures (Inspector gate 2)

- BoundaryViolation(source_module: str, target_module: str, rule_kind: str, file_path: str, line: int)  # unchanged
- format_report(violations: Sequence[BoundaryViolation]) -> str  # unchanged
- format_violation(violation: BoundaryViolation) -> str  # unchanged
- format_report_json(violations: Sequence[BoundaryViolation]) -> str  # NEW
- run(target_dir: str, boundaries_file: str, output_format: str = "text") -> int  # changed from run(target_dir: str, boundaries_file: str) -> int
- main(argv: Sequence[str]) -> int  # unchanged signature; internal argparse adds --format {text,json}
