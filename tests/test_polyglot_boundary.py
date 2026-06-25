import os
import unittest

from scripts.codegraph_index import observed_import_edges
from scripts.codegraph_scanner import scan_imports_from_index
from src.adapters.boundaries.boundaries_config_loader import load_module_rules
from src.application.boundaries.lint_boundaries import LintBoundaries

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DB = os.path.join(REPO_ROOT, ".codegraph", "codegraph.db")
FIXTURE_BOUNDARIES = os.path.join(REPO_ROOT, "examples", "ts-mini", "boundaries.yaml")


def _ts_mini_indexed():
    if not os.path.isfile(REAL_DB):
        return False
    try:
        return any(
            "examples/ts-mini" in o.source_file for o in observed_import_edges(REAL_DB)
        )
    except Exception:
        return False


class PolyglotBoundaryTest(unittest.TestCase):
    """Iteration 9a headline: the harness's boundary check works on a non-Python
    language because it reads import edges from CodeGraph, not Python `ast`."""

    @unittest.skipUnless(
        _ts_mini_indexed(),
        "examples/ts-mini not in the CodeGraph index; run `codegraph sync`",
    )
    def test_forbidden_typescript_edge_is_flagged(self):
        module_rules = load_module_rules(FIXTURE_BOUNDARIES)
        use_case = LintBoundaries()
        rule_set = use_case.build_rule_set(module_rules)
        # Read the real CodeGraph index (multi-language); map TS files to modules
        # via the same domain rule set used for Python.
        scan = scan_imports_from_index(rule_set, db_path=REAL_DB)
        violations = use_case.run(module_rules, scan.edges, scan.parse_failures)
        ts_violations = [v for v in violations if "ts-mini" in v.file_path]
        self.assertTrue(
            any(
                v.source_module == "domain"
                and v.target_module == "adapters"
                and v.rule_kind == "must_not_depend_on"
                for v in ts_violations
            ),
            "expected a TS domain -> adapters must_not_depend_on violation, got %r"
            % (ts_violations,),
        )
        # the violation carries the TS source file + line, same contract as Python
        v = ts_violations[0]
        self.assertTrue(v.file_path.endswith(".ts"))
        self.assertEqual(v.file_path, "examples/ts-mini/domain/core.ts")


if __name__ == "__main__":
    unittest.main()
