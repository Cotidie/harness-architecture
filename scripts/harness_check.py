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

import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import yaml

from scripts.codegraph_index import CodegraphIndexError
from scripts.codegraph_scanner import scan_imports_from_index
from scripts.drift_scan import compute_drift
from scripts.drift_scan import format_report as format_drift
from scripts.harness_paths import HarnessPathsError, Paths, resolve_paths
from scripts.intended_diff import compute_diff
from scripts.intended_diff import format_report as format_diff

from src.adapters.boundaries.boundaries_config_loader import (
    BoundariesConfigError,
    load_module_rules,
)
from src.adapters.boundaries.violation_reporter import format_report as format_violations
from src.application.boundaries.lint_boundaries import LintBoundaries

# Per-check could-not-run errors that map to an `error` status, never a crash.
_COULD_NOT_RUN = (
    HarnessPathsError,
    CodegraphIndexError,
    BoundariesConfigError,
    FileNotFoundError,
    NotADirectoryError,
    OSError,
    ValueError,
    yaml.YAMLError,
)


def _codegraph_scan(_target_dir, rule_set):
    """The harness's observed-edge source: CodeGraph index, not Python `ast`.
    Signature matches the ast `scan_imports(target_dir, rule_set)` seam so it
    drops into `_run_linter` and `compute_drift`; the target dir is unused
    because the index already covers the whole repo (the rule globs scope it)."""
    return scan_imports_from_index(rule_set)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "clean" | "drift" | "error"
    report_text: str


def _run_linter(source_dir: str, boundaries: str, scan_fn=_codegraph_scan) -> Tuple[bool, str]:
    """Run the boundaries linter without the CLI's print/exit; return
    (clean, report_text). The observed edges come from `scan_fn` (the CodeGraph
    scanner by default, so the harness's boundary check is polyglot). Raises a
    could-not-run error on a bad tree or a missing/stale index."""
    module_rules = load_module_rules(boundaries)
    use_case = LintBoundaries()
    rule_set = use_case.build_rule_set(module_rules)
    scan = scan_fn(source_dir, rule_set)
    if scan.matched_file_count == 0:
        raise BoundariesConfigError(
            "no files under %r matched any module path glob; nothing was checked"
            % (source_dir,)
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


CHECK_NAMES = ("boundaries", "drift_scan", "intended_diff")


def compute_results(
    repo_root: str = ".", only: Optional[Set[str]] = None, scan_fn=_codegraph_scan
) -> List[CheckResult]:
    # `scan_fn(target_dir, rule_set) -> ScanResult` is the observed-edge source.
    # Default is the CodeGraph scanner (polyglot, production). Tests of the
    # aggregation logic inject the `ast` scanner so they can run on un-indexed
    # temp trees.
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
            clean, text = _run_linter(paths.source_dir, paths.boundaries, scan_fn=scan_fn)
            return ("clean" if clean else "drift"), text

        def _drift():
            report = compute_drift(
                paths.source_dir, paths.boundaries, scan_imports_fn=scan_fn
            )
            return ("drift" if report.has_drift else "clean"), format_drift(report)

        def _intended():
            report = compute_diff(
                paths.source_dir, paths.contracts, paths.domain_model
            )
            return ("drift" if report.has_drift else "clean"), format_diff(report)

        checks = [
            ("boundaries", _linter),
            ("drift_scan", _drift),
            ("intended_diff", _intended),
        ]
        if only is not None:
            checks = [(name, run) for name, run in checks if name in only]
        return [_check(name, run) for name, run in checks]
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
    parser = argparse.ArgumentParser(prog="python -m scripts.harness_check")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument(
        "--only",
        default=None,
        help="comma-separated subset of checks: %s" % ",".join(CHECK_NAMES),
    )
    args = parser.parse_args(argv)
    only = None
    if args.only:
        only = {part.strip() for part in args.only.split(",") if part.strip()}
        unknown = only - set(CHECK_NAMES)
        if unknown:
            sys.stderr.write(
                "unknown check(s): %s (known: %s)\n"
                % (", ".join(sorted(unknown)), ", ".join(CHECK_NAMES))
            )
            return 2
    results = compute_results(args.repo_root, only=only)
    print(format_report(results))
    return aggregate_exit(results)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
