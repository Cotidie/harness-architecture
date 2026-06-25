"""Harness tooling: one entrypoint for every deterministic check.

Consolidates the three committed checks (boundaries linter, drift_scan,
intended_diff) behind a single command that reads its paths from the convention
profile (`source_root`) instead of hardcoding `src/`. Runs them against the
resolved paths, aggregates the outcomes into one report, and returns one exit
code: 2 if any check could not run, 1 if any check found drift, else 0.

`detect_profile` is intentionally NOT here: it is a survey-time seed, not a
per-run drift check. This surface is deterministic (no CodeGraph query), so the
orchestrator runs it unmetered.

The three sub-checks keep their own functions/CLIs and tests; this module is a
thin aggregator (path resolution + invocation + report combination) plus a small
wrapper that adapts the boundaries linter to a (clean, report) result without
the CLI's print/exit.
"""

import os
import sys
from dataclasses import dataclass
from typing import List, Tuple

import yaml

from scripts.drift_scan import compute_drift
from scripts.drift_scan import format_report as format_drift
from scripts.harness_paths import HarnessPathsError, Paths, resolve_paths
from scripts.intended_diff import compute_diff
from scripts.intended_diff import format_report as format_diff

from src.adapters.boundaries.boundaries_config_loader import (
    BoundariesConfigError,
    load_module_rules,
)
from src.adapters.boundaries.python_import_scanner import scan_imports
from src.adapters.boundaries.violation_reporter import format_report as format_violations
from src.application.boundaries.lint_boundaries import LintBoundaries

# Per-check could-not-run errors that map to an `error` status, never a crash.
_COULD_NOT_RUN = (
    HarnessPathsError,
    BoundariesConfigError,
    FileNotFoundError,
    NotADirectoryError,
    OSError,
    ValueError,
    yaml.YAMLError,
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "clean" | "drift" | "error"
    report_text: str


def _run_linter(source_dir: str, boundaries: str) -> Tuple[bool, str]:
    """Run the boundaries linter without the CLI's print/exit; return
    (clean, report_text). Raises a could-not-run error on a bad tree."""
    module_rules = load_module_rules(boundaries)
    use_case = LintBoundaries()
    rule_set = use_case.build_rule_set(module_rules)
    scan = scan_imports(source_dir, rule_set)
    if scan.matched_file_count == 0:
        raise BoundariesConfigError(
            "no Python files under %r matched any module path glob; "
            "nothing was checked" % (source_dir,)
        )
    violations = use_case.run(module_rules, scan.edges, scan.parse_failures)
    return (not violations), format_violations(violations)


def _check(name: str, run) -> CheckResult:
    """Run one check closure, mapping a could-not-run error to status=error."""
    try:
        status, report_text = run()
    except _COULD_NOT_RUN as exc:
        return CheckResult(name, "error", "could not run: %s" % (exc,))
    return CheckResult(name, status, report_text)


def compute_results(repo_root: str = ".") -> List[CheckResult]:
    # Resolve once; a profile/path failure means no check can run.
    prev = os.getcwd()
    abs_root = os.path.abspath(repo_root)
    os.chdir(abs_root)
    try:
        try:
            paths: Paths = resolve_paths(".")
        except _COULD_NOT_RUN as exc:
            return [CheckResult("profile", "error", "could not run: %s" % (exc,))]

        def _linter():
            clean, text = _run_linter(paths.source_dir, paths.boundaries)
            return ("clean" if clean else "drift"), text

        def _drift():
            report = compute_drift(paths.source_dir, paths.boundaries)
            return ("drift" if report.has_drift else "clean"), format_drift(report)

        def _intended():
            report = compute_diff(
                paths.source_dir, paths.contracts, paths.domain_model
            )
            return ("drift" if report.has_drift else "clean"), format_diff(report)

        return [
            _check("boundaries", _linter),
            _check("drift_scan", _drift),
            _check("intended_diff", _intended),
        ]
    finally:
        os.chdir(prev)


def aggregate_exit(results: List[CheckResult]) -> int:
    if any(r.status == "error" for r in results):
        return 2
    if any(r.status == "drift" for r in results):
        return 1
    return 0


def format_report(results: List[CheckResult]) -> str:
    lines = ["# Harness check", ""]
    for result in results:
        lines.append("## %s: %s" % (result.name, result.status.upper()))
        lines.append(result.report_text.rstrip())
        lines.append("")
    code = aggregate_exit(results)
    verdict = {0: "ALL CLEAN", 1: "DRIFT FOUND", 2: "COULD NOT RUN"}[code]
    lines.append("## Summary")
    lines.append(
        "%s (%s)"
        % (verdict, ", ".join("%s=%s" % (r.name, r.status) for r in results))
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    repo_root = argv[0] if argv else "."
    results = compute_results(repo_root)
    print(format_report(results))
    return aggregate_exit(results)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
