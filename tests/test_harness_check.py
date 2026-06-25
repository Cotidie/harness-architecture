import contextlib
import os
import tempfile
import textwrap
import unittest

from scripts.harness_check import aggregate_exit, compute_results

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.contextmanager
def _tree(files):
    with tempfile.TemporaryDirectory() as root:
        for relpath, content in files.items():
            full = os.path.join(root, relpath)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(content)
        yield root


def _harness_files(layer="src", overrides=None):
    """A minimal but valid harness tree: profile + the three intended YAMLs +
    a clean layered source tree under `layer`/. ALIGNED by construction."""
    boundaries = textwrap.dedent(
        """\
        modules:
          domain:
            path: "%(L)s/domain/**"
            may_depend_on: []
            must_not_depend_on: [adapters]
          contracts:
            path: "%(L)s/contracts/**"
            may_depend_on: []
            must_not_depend_on: []
          adapters:
            path: "%(L)s/adapters/**"
            may_depend_on: [domain, contracts]
            must_not_depend_on: []
        """
        % {"L": layer}
    )
    contracts_yaml = textwrap.dedent(
        """\
        contracts:
          - name: Dto
            layer: contracts
            module: %s/contracts/dto.py
            crosses: "x"
            fields:
              value: int
        """
        % layer
    )
    files = {
        ".architecture/profile.yaml": "label: t\nlanguage: python\nsource_root: %s\n" % layer,
        ".architecture/boundaries.yaml": boundaries,
        ".architecture/contracts.yaml": contracts_yaml,
        ".architecture/domain-model.yaml": "domain_classes: []\n",
        "%s/domain/__init__.py" % layer: "",
        "%s/domain/core.py" % layer: "x = 1\n",
        "%s/contracts/__init__.py" % layer: "",
        "%s/contracts/dto.py" % layer: (
            "from dataclasses import dataclass\n\n\n"
            "@dataclass(frozen=True)\nclass Dto:\n    value: int\n"
        ),
        "%s/adapters/__init__.py" % layer: "",
        "%s/adapters/io.py" % layer: "import %s.domain.core\n" % layer,
    }
    if overrides:
        files.update(overrides)
    return files


def _by_name(results, name):
    return next(r for r in results if r.name == name)


class HarnessCheckTest(unittest.TestCase):
    def test_real_repo_all_clean(self):
        results = compute_results(REPO_ROOT)
        self.assertEqual(aggregate_exit(results), 0, results)
        self.assertTrue(all(r.status == "clean" for r in results), results)

    def test_clean_temp_tree_exit_0(self):
        with _tree(_harness_files()) as root:
            results = compute_results(root)
        self.assertEqual(aggregate_exit(results), 0, results)

    def test_forbidden_edge_makes_linter_drift(self):
        overrides = {"src/domain/core.py": "import src.adapters.io\n"}
        with _tree(_harness_files(overrides=overrides)) as root:
            results = compute_results(root)
        self.assertEqual(aggregate_exit(results), 1, results)
        linter = _by_name(results, "boundaries")
        self.assertEqual(linter.status, "drift")

    def test_contract_mismatch_makes_intended_diff_drift(self):
        # Declare a different field type than the code defines.
        bad_contracts = textwrap.dedent(
            """\
            contracts:
              - name: Dto
                layer: contracts
                module: src/contracts/dto.py
                crosses: "x"
                fields:
                  value: str
            """
        )
        overrides = {".architecture/contracts.yaml": bad_contracts}
        with _tree(_harness_files(overrides=overrides)) as root:
            results = compute_results(root)
        self.assertEqual(aggregate_exit(results), 1, results)
        diff = _by_name(results, "intended_diff")
        self.assertEqual(diff.status, "drift")

    def test_missing_profile_is_could_not_run_exit_2(self):
        with _tree({"README.md": "# no profile\n"}) as root:
            results = compute_results(root)
        self.assertEqual(aggregate_exit(results), 2, results)

    def test_only_runs_just_the_named_check(self):
        # gate 1 uses `--only boundaries`: a contract mismatch (intended_diff
        # drift) must NOT make a boundaries-only run report drift.
        bad_contracts = textwrap.dedent(
            """\
            contracts:
              - name: Dto
                layer: contracts
                module: src/contracts/dto.py
                crosses: "x"
                fields:
                  value: str
            """
        )
        overrides = {".architecture/contracts.yaml": bad_contracts}
        with _tree(_harness_files(overrides=overrides)) as root:
            results = compute_results(root, only={"boundaries"})
        self.assertEqual([r.name for r in results], ["boundaries"])
        self.assertEqual(aggregate_exit(results), 0, results)

    def test_profile_driven_non_src_layout(self):
        # source_root = app, not src: the checks must target app/ and be clean.
        with _tree(_harness_files(layer="app")) as root:
            results = compute_results(root)
        self.assertEqual(aggregate_exit(results), 0, results)
        self.assertTrue(all(r.status == "clean" for r in results), results)


if __name__ == "__main__":
    unittest.main()
