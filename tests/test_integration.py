import os
import unittest

from src.adapters.boundaries.boundaries_config_loader import load_module_rules
from src.adapters.boundaries.python_import_scanner import scan_imports
from src.application.boundaries.lint_boundaries import LintBoundaries
from src.adapters.boundaries import cli


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lint(target_dir, boundaries_file):
    target = os.path.join(REPO_ROOT, target_dir)
    boundaries = os.path.join(REPO_ROOT, boundaries_file)
    module_rules = load_module_rules(boundaries)
    use_case = LintBoundaries()
    rule_set = use_case.build_rule_set(module_rules)
    # Scan with a repo-root-relative target so paths match the YAML globs.
    cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        edges = scan_imports(target_dir, rule_set)
    finally:
        os.chdir(cwd)
    return use_case.run(module_rules, edges)


class SampleIntegrationTests(unittest.TestCase):
    def test_reports_exactly_the_planted_violation(self):
        violations = _lint("sample", "sample/boundaries.yaml")
        self.assertEqual(len(violations), 1, msg=str(violations))
        v = violations[0]
        self.assertEqual(v.source_module, "domain")
        self.assertEqual(v.target_module, "contracts")
        self.assertEqual(v.rule_kind, "must_not_depend_on")
        self.assertEqual(
            v.file_path, "sample/domain/route_risk_policy.py"
        )
        self.assertEqual(v.line, 9)

    def test_cli_exit_code_nonzero_on_sample(self):
        cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            code = cli.run("sample", "sample/boundaries.yaml")
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 1)


class CleanCaseTests(unittest.TestCase):
    def test_no_violations_when_only_allowed_edges(self):
        # Scope to the application subtree, which has only allowed edges.
        violations = _lint("sample/application", "sample/boundaries.yaml")
        self.assertEqual(violations, [])


class SelfCheckTests(unittest.TestCase):
    def test_src_obeys_its_own_intended_boundaries(self):
        violations = _lint("src", ".architecture/boundaries.yaml")
        self.assertEqual(violations, [], msg=str(violations))

    def test_cli_exit_code_zero_on_src(self):
        cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            code = cli.run("src", ".architecture/boundaries.yaml")
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
