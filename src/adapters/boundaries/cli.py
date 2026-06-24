"""Adapter: CLI entry point for the boundaries linter.

Usage:
    python -m src.adapters.boundaries.cli <target_dir> <boundaries_file>

Wires loader + rule set + scanner + use case + reporter, prints the report, and
sets the process exit code (non-zero when any violation exists, zero otherwise).
"""

import sys
from typing import List, Sequence

from src.adapters.boundaries.boundaries_config_loader import load_module_rules
from src.adapters.boundaries.python_import_scanner import scan_imports
from src.adapters.boundaries.violation_reporter import format_report
from src.application.boundaries.lint_boundaries import LintBoundaries


def run(target_dir: str, boundaries_file: str) -> int:
    module_rules = load_module_rules(boundaries_file)
    use_case = LintBoundaries()
    rule_set = use_case.build_rule_set(module_rules)
    import_edges = scan_imports(target_dir, rule_set)
    violations = use_case.run(module_rules, import_edges)
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
    return run(args[0], args[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
