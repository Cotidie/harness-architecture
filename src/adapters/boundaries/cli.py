"""Adapter: CLI entry point for the boundaries linter.

Usage:
    python -m src.adapters.boundaries.cli <target_dir> <boundaries_file>

Wires loader + rule set + scanner + use case + reporter, prints the report, and
sets the process exit code (non-zero when any violation exists, zero otherwise).
"""

import argparse
import sys
from typing import Sequence

import yaml

from src.adapters.boundaries.boundaries_config_loader import (
    BoundariesConfigError,
    load_module_rules,
)
from src.adapters.boundaries.python_import_scanner import scan_imports
from src.adapters.boundaries.violation_reporter import (
    format_report,
    format_report_json,
)
from src.application.boundaries.lint_boundaries import LintBoundaries


def run(
    target_dir: str, boundaries_file: str, output_format: str = "text"
) -> int:
    module_rules = load_module_rules(boundaries_file)
    use_case = LintBoundaries()
    rule_set = use_case.build_rule_set(module_rules)
    scan = scan_imports(target_dir, rule_set)
    if scan.matched_file_count == 0:
        # Loud-fail the HIGH false negative: a tree that matches no module
        # glob (wrong cwd, absolute path, empty package) must never report a
        # silent clean pass. This is a could-not-run condition (exit 2).
        raise BoundariesConfigError(
            "no Python files under %r matched any module path glob; "
            "nothing was checked" % (target_dir,)
        )
    violations = use_case.run(module_rules, scan.edges, scan.parse_failures)
    formatter = format_report_json if output_format == "json" else format_report
    print(formatter(violations))
    return 1 if violations else 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.adapters.boundaries.cli",
    )
    parser.add_argument("target_dir")
    parser.add_argument("boundaries_file")
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    try:
        parsed = parser.parse_args(list(argv))
    except SystemExit:
        # argparse exits the process on misuse (missing args, invalid
        # --format value). The CLI is the composition root and owns the
        # exit code: misuse maps to exit 2, never a propagated SystemExit.
        return 2
    try:
        return run(
            parsed.target_dir, parsed.boundaries_file, parsed.output_format
        )
    except (
        FileNotFoundError,
        OSError,
        BoundariesConfigError,
        yaml.YAMLError,
    ) as exc:
        # The CLI is the composition root: it owns process exit code and
        # stderr. A could-not-run failure surfaces as a clean message, never a
        # traceback, and maps to exit 2.
        sys.stderr.write("error: %s\n" % (exc,))
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
