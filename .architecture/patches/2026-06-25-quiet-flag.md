# Architecture Patch: `--quiet` flag for the boundaries linter CLI

## 1. Feature request

Add a `--quiet` flag to the boundaries linter CLI. With `--quiet`, on a CLEAN
run (no violations) the CLI suppresses the human-readable
"No boundary violations found." line and prints nothing to stdout; exit codes
are unchanged (0 clean, 1 findings, 2 could-not-run). When violations exist,
output is unchanged. `--quiet` composes with `--format` (quiet only suppresses
the clean-run message).

## 2. Observed architecture (from CodeGraph, 1 query)

- Affected module: `adapters` (`src/adapters/boundaries/cli.py`). The CLI is the
  composition root: it owns argparse, the single `print(...)` of the report, and
  the process exit code.
- Affected symbols (verbatim from the query):
  - `run(target_dir: str, boundaries_file: str, output_format: str = "text") -> int`
    at `src/adapters/boundaries/cli.py:28`. It selects `format_report_json` vs
    `format_report`, does the only `print(...)` (line 45), and returns
    `1 if violations else 0`. The could-not-run path raises
    `BoundariesConfigError` (mapped to exit 2 by `main`).
  - `main(argv: Sequence[str]) -> int` at `src/adapters/boundaries/cli.py:49`.
    Builds the argparse parser (`target_dir`, `boundaries_file`, `--format`),
    maps argparse misuse to exit 2, calls `run(...)`, and maps could-not-run
    exceptions to exit 2.
- The clean-run message text lives in the reporter (`format_report` /
  `format_report_json`), invoked at `cli.py:44-45`; the CLI prints whatever the
  formatter returns. Quiet suppression must therefore happen in `run` (skip the
  print on a clean run), not in the reporter.
- Domain (`BoundaryRuleSet`, `BoundaryDecision`) and contracts
  (`BoundaryViolation`, `ImportEdge`, `ModuleRule`) are not touched.

## 3. Intended architecture (from docs)

- `adapters` may depend on `application, domain, contracts, shared`
  (`boundaries.yaml`). A change confined to the CLI adapter touches no boundary.
- The CLI is the composition root; owning argparse, stdout, and exit codes here
  is the intended placement. No business behavior is added, so no domain class
  is required (`domain-model.md`).
- No data crosses a new boundary; `--quiet` is a process-local presentation
  toggle, so no new contract class is required (`data-contracts.md`).

## 4. Reconciliation decision

`ALIGNED`. Observed CLI structure matches intended: argparse, the single print,
and exit-code ownership all live in the `adapters` CLI composition root, which
is exactly where this presentation toggle belongs. No boundary, contract, or
domain rule is involved. Proceed with the feature as a lite patch.

Unrelated observed drift: none surfaced by the query.

## 5-8. Module / dependency / domain / contract changes

None. This is a lite patch: one new argparse flag plus a conditional around the
existing clean-run `print(...)` inside the `adapters` CLI. No module is created,
moved, or removed; no allowed/forbidden edge changes; no domain class or method
changes; no contract is created, expanded, merged, split, renamed, or versioned.

The seam signatures of the two existing public entry points (`run`, `main`)
change only by adding an optional `quiet` parameter / flag; see the seam block
below for `current -> proposed`.

## 9. Files allowed to edit

- `src/adapters/boundaries/cli.py` : add the `--quiet` argparse flag in `main`,
  thread a `quiet: bool = False` parameter into `run`, and guard the clean-run
  print so a clean run under `--quiet` prints nothing to stdout. Exit codes and
  the violations-present output path are unchanged.
- `tests/test_integration.py` : add the tests listed in section 10 (this file
  already drives the CLI via `_main_on_sample` / `main`).

## 10. Tests required

Boundary/integration (CLI behavior; no domain or contract tests needed):

- Clean run with `--quiet`: stdout is empty, exit code is 0.
- Clean run without `--quiet`: stdout still contains the
  "No boundary violations found." line, exit code 0 (regression guard).
- Violations present with `--quiet`: stdout output is identical to the non-quiet
  run, exit code 1 (quiet does not suppress findings).
- `--quiet` composes with `--format json`: clean run prints nothing; a run with
  violations prints the unchanged JSON report.
- `--quiet` does not affect could-not-run: a no-match / load-error run still
  writes the stderr `error: ...` line and exits 2.

## 11. Risks

- Low. The only behavioral change is suppressing one stdout line on the clean
  path under an opt-in flag. Risk is over-suppression: `--quiet` must NOT silence
  the violations output (exit 1) nor the stderr error line (exit 2). The tests in
  section 10 pin both. Default behavior (no `--quiet`) is unchanged.

- [x] Approved (human, 2026-06-25)

## Seam signatures (Inspector gate 2)

- `run(target_dir: str, boundaries_file: str, output_format: str = "text") -> int` -> `run(target_dir: str, boundaries_file: str, output_format: str = "text", quiet: bool = False) -> int`   # current -> proposed
- `main(argv: Sequence[str]) -> int` -> `main(argv: Sequence[str]) -> int`   # unchanged (signature); adds `--quiet` argparse flag (`dest="quiet"`, `action="store_true"`, default `False`) threaded into `run`
