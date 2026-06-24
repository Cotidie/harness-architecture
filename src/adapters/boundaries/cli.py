"""Adapter: CLI entry point for the boundaries linter.

Usage:
    python -m src.adapters.boundaries.cli <target_dir> <boundaries_file>

Wires loader + rule set + scanner + use case + reporter, prints the report, and
sets the process exit code (non-zero when any violation exists, zero otherwise).
"""

import sys
from typing import List, Sequence

import yaml

from src.adapters.boundaries.boundaries_config_loader import (
    BoundariesConfigError,
    load_module_rules,
)
from src.adapters.boundaries.python_import_scanner import scan_imports
from src.adapters.boundaries.violation_reporter import format_report
from src.application.boundaries.lint_boundaries import LintBoundaries


def run(target_dir: str, boundaries_file: str) -> int:
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
    print(format_report(violations))
    return 1 if violations else 0


def main(argv: Sequence[str]) -> int:
    args: List[str] = list(argv)
    if len(args) != 2:
        sys.stderr.write(
            "usage: python -m src.adapters.boundaries.cli "
            "<target_dir> <boundaries_file>\n"
        )
        return 2
    try:
        return run(args[0], args[1])
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
