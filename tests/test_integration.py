import contextlib
import io
import json
import os
import tempfile
import textwrap
import unittest

from src.adapters.boundaries.boundaries_config_loader import load_module_rules
from src.adapters.boundaries.python_import_scanner import scan_imports
from src.application.boundaries.lint_boundaries import LintBoundaries
from src.adapters.boundaries import cli


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.contextmanager
def _capture():
    """Capture stdout and stderr while running the CLI main entry point."""
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


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
        scan = scan_imports(target_dir, rule_set)
    finally:
        os.chdir(cwd)
    return use_case.run(module_rules, scan.edges, scan.parse_failures)


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


_BOUNDARIES_YAML = textwrap.dedent(
    """\
    modules:
      domain:
        path: "pkg/domain/**"
        must_not_depend_on: ["contracts"]
      contracts:
        path: "pkg/contracts/**"
    """
)


class ErrorExitCodeTests(unittest.TestCase):
    def test_nonexistent_target_dir_errors_exit_2(self):
        boundaries = os.path.join(REPO_ROOT, "sample/boundaries.yaml")
        with _capture() as (out, err):
            code = cli.main(["/does/not/exist", boundaries])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("No boundary violations found.", out.getvalue())

    def test_target_is_not_a_directory_errors_exit_2(self):
        boundaries = os.path.join(REPO_ROOT, "sample/boundaries.yaml")
        # Point the target at a file, not a directory.
        with _capture() as (out, err):
            code = cli.main([boundaries, boundaries])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())

    def test_missing_config_file_errors_cleanly_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _capture() as (out, err):
                code = cli.main([tmp, "/no/such/boundaries.yaml"])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_malformed_yaml_errors_cleanly_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write("modules: [this: is, : broken\n")
            with _capture() as (out, err):
                code = cli.main([tmp, cfg])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_missing_modules_key_errors_cleanly_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write("other: {}\n")
            with _capture() as (out, err):
                code = cli.main([tmp, cfg])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_missing_path_key_errors_cleanly_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write("modules:\n  domain:\n    must_not_depend_on: []\n")
            with _capture() as (out, err):
                code = cli.main([tmp, cfg])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_bad_arg_count_exit_2(self):
        with _capture() as (out, err):
            code = cli.main(["only-one-arg"])
        self.assertEqual(code, 2)


class ZeroMatchedFilesTests(unittest.TestCase):
    def test_target_matching_no_module_glob_errors_exit_2(self):
        # A target dir with .py files that match no module path glob must
        # loud-fail (exit 2), never silently report a clean tree.
        with tempfile.TemporaryDirectory() as tmp:
            unmatched = os.path.join(tmp, "elsewhere")
            os.makedirs(unmatched)
            with open(os.path.join(unmatched, "thing.py"), "w") as handle:
                handle.write("x = 1\n")
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write(_BOUNDARIES_YAML)
            with _capture() as (out, err):
                code = cli.main([unmatched, cfg])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("No boundary violations found.", out.getvalue())

    def test_empty_tree_errors_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, "empty")
            os.makedirs(empty)
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write(_BOUNDARIES_YAML)
            with _capture() as (out, err):
                code = cli.main([empty, cfg])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())


class ParseFailureTests(unittest.TestCase):
    def _build_tree(self, tmp):
        """A tree with one matched-module syntax-error file plus a clean one."""
        domain = os.path.join(tmp, "pkg", "domain")
        os.makedirs(domain)
        with open(os.path.join(domain, "broken.py"), "w") as handle:
            handle.write("def broken(:\n    pass\n")
        with open(os.path.join(domain, "clean.py"), "w") as handle:
            handle.write("import pkg.contracts.thing\n")
        contracts = os.path.join(tmp, "pkg", "contracts")
        os.makedirs(contracts)
        with open(os.path.join(contracts, "thing.py"), "w") as handle:
            handle.write("x = 1\n")
        cfg = os.path.join(tmp, "boundaries.yaml")
        with open(cfg, "w", encoding="utf-8") as handle:
            handle.write(_BOUNDARIES_YAML)
        return cfg

    def test_syntax_error_file_reported_and_other_files_scanned(self):
        # The scanner must keep scanning past a syntax-error file. Run from
        # within tmp so the relative paths match the YAML globs.
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._build_tree(tmp)
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with _capture() as (out, err):
                    code = cli.main(["pkg", "boundaries.yaml"])
            finally:
                os.chdir(cwd)
        # A parse failure is a reportable finding: exit 1, not 2.
        self.assertEqual(code, 1)
        output = out.getvalue()
        self.assertIn("parse_error", output)
        self.assertIn("broken.py", output)
        # The clean.py import was still scanned and flagged the planted
        # domain -> contracts violation.
        self.assertIn("must_not_depend_on", output)


_MAY_ONLY_BOUNDARIES_YAML = textwrap.dedent(
    """\
    modules:
      application:
        path: "pkg/application/**"
        may_only_depend_on: ["domain"]
      domain:
        path: "pkg/domain/**"
      adapters:
        path: "pkg/adapters/**"
    """
)


class MayOnlyDependOnIntegrationTests(unittest.TestCase):
    def test_allowlist_violation_reported_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            application = os.path.join(tmp, "pkg", "application")
            os.makedirs(application)
            with open(os.path.join(application, "use_case.py"), "w") as handle:
                handle.write("import pkg.adapters.thing\n")
            adapters = os.path.join(tmp, "pkg", "adapters")
            os.makedirs(adapters)
            with open(os.path.join(adapters, "thing.py"), "w") as handle:
                handle.write("x = 1\n")
            domain = os.path.join(tmp, "pkg", "domain")
            os.makedirs(domain)
            with open(os.path.join(domain, "core.py"), "w") as handle:
                handle.write("x = 1\n")
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write(_MAY_ONLY_BOUNDARIES_YAML)

            module_rules = load_module_rules(cfg)
            use_case = LintBoundaries()
            rule_set = use_case.build_rule_set(module_rules)
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                scan = scan_imports("pkg", rule_set)
            finally:
                os.chdir(cwd)
            violations = use_case.run(
                module_rules, scan.edges, scan.parse_failures
            )

        self.assertEqual(len(violations), 1, msg=str(violations))
        v = violations[0]
        self.assertEqual(v.source_module, "application")
        self.assertEqual(v.target_module, "adapters")
        self.assertEqual(v.rule_kind, "may_only_depend_on")


class CleanTreeExitTests(unittest.TestCase):
    def test_clean_tree_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            domain = os.path.join(tmp, "pkg", "domain")
            os.makedirs(domain)
            with open(os.path.join(domain, "ok.py"), "w") as handle:
                handle.write("x = 1\n")
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write(_BOUNDARIES_YAML)
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with _capture() as (out, err):
                    code = cli.main(["pkg", "boundaries.yaml"])
            finally:
                os.chdir(cwd)
        self.assertEqual(code, 0)
        self.assertIn("No boundary violations found.", out.getvalue())


class FormatFlagTests(unittest.TestCase):
    """CLI --format selection, exit codes, and default-text behavior."""

    def _main_on_sample(self, *extra):
        # The sample YAML globs are repo-root relative, so run from there
        # with relative paths (matches the existing sample CLI tests).
        cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            with _capture() as (out, err):
                code = cli.main(
                    ["sample", "sample/boundaries.yaml", *extra]
                )
        finally:
            os.chdir(cwd)
        return code, out, err

    def test_default_no_flag_prints_text_on_sample(self):
        code, out, err = self._main_on_sample()
        self.assertEqual(code, 1)
        output = out.getvalue()
        self.assertIn("boundary violation(s) found.", output)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(output)

    def test_format_text_matches_default(self):
        code, out, err = self._main_on_sample("--format", "text")
        self.assertEqual(code, 1)
        self.assertIn("boundary violation(s) found.", out.getvalue())

    def test_format_json_prints_parseable_json_no_text(self):
        code, out, err = self._main_on_sample("--format", "json")
        self.assertEqual(code, 1)
        output = out.getvalue()
        payload = json.loads(output)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["source_module"], "domain")
        self.assertEqual(payload[0]["target_module"], "contracts")
        self.assertEqual(payload[0]["rule_kind"], "must_not_depend_on")
        self.assertNotIn("boundary violation(s) found.", output)

    def test_invalid_format_value_exit_2(self):
        with _capture() as (out, err):
            code = cli.main(
                [
                    os.path.join(REPO_ROOT, "sample"),
                    os.path.join(REPO_ROOT, "sample/boundaries.yaml"),
                    "--format",
                    "xml",
                ]
            )
        self.assertEqual(code, 2)

    def test_clean_tree_json_exit_0_empty_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            domain = os.path.join(tmp, "pkg", "domain")
            os.makedirs(domain)
            with open(os.path.join(domain, "ok.py"), "w") as handle:
                handle.write("x = 1\n")
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write(_BOUNDARIES_YAML)
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with _capture() as (out, err):
                    code = cli.main(["pkg", "boundaries.yaml", "--format", "json"])
            finally:
                os.chdir(cwd)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue()), [])

    def test_could_not_run_json_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, "empty")
            os.makedirs(empty)
            cfg = os.path.join(tmp, "boundaries.yaml")
            with open(cfg, "w", encoding="utf-8") as handle:
                handle.write(_BOUNDARIES_YAML)
            with _capture() as (out, err):
                code = cli.main([empty, cfg, "--format", "json"])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())

    def test_run_accepts_output_format_json(self):
        cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            with _capture() as (out, err):
                code = cli.run(
                    "sample", "sample/boundaries.yaml", output_format="json"
                )
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 1)
        self.assertEqual(len(json.loads(out.getvalue())), 1)


if __name__ == "__main__":
    unittest.main()
