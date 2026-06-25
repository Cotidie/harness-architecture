import contextlib
import os
import tempfile
import textwrap
import unittest

from scripts.intended_diff import compute_diff, _observed_domain


@contextlib.contextmanager
def _tree(files):
    """Materialize {relpath: content} under a temp dir, chdir in so the diff
    resolves source and YAML the way the harness runs it."""
    with tempfile.TemporaryDirectory() as root:
        for relpath, content in files.items():
            full = os.path.join(root, relpath)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(textwrap.dedent(content))
        cwd = os.getcwd()
        os.chdir(root)
        try:
            yield root
        finally:
            os.chdir(cwd)


# A minimal contracts.yaml + one real contract source, ALIGNED by construction.
CONTRACT_SRC = """\
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ModuleRule:
    name: str
    path_glob: str
    may_depend_on: Tuple[str, ...]
"""

CONTRACTS_YAML = """\
contracts:
  - name: ModuleRule
    layer: contracts
    module: src/contracts/x.py
    crosses: "loader -> application"
    fields:
      name: str
      path_glob: str
      may_depend_on: "Tuple[str, ...]"
"""

EMPTY_DOMAIN_YAML = "domain_classes: []\n"


def _base_files(extra=None):
    files = {
        "src/contracts/__init__.py": "",
        "src/contracts/x.py": CONTRACT_SRC,
        "contracts.yaml": CONTRACTS_YAML,
        "domain-model.yaml": EMPTY_DOMAIN_YAML,
    }
    if extra:
        files.update(extra)
    return files


class IntendedDiffTest(unittest.TestCase):
    def _files(self, domain_method_sig="(self, path: str) -> Optional[str]"):
        """Build a file dict with a domain class whose method has the given sig."""
        domain_src = textwrap.dedent(
            """\
            from typing import Optional


            class Router:
                def module_for_path%s:
                    return None
            """
        ) % domain_method_sig
        domain_yaml = textwrap.dedent(
            """\
            domain_classes:
              - name: Router
                layer: domain
                module: src/domain/router.py
                responsibility: "route paths"
                invariants: []
                methods:
                  module_for_path: "(path: str) -> Optional[str]"
            """
        )
        return _base_files(
            {
                "src/domain/__init__.py": "",
                "src/domain/router.py": domain_src,
                "domain-model.yaml": domain_yaml,
            }
        )

    def test_domain_observer_seam_flags_signature_drift(self):
        # declared says module_for_path takes (path: str); code says (path: int) -> drift
        with _tree(self._files(domain_method_sig="(self, path: int) -> Optional[str]")):
            report = compute_diff(
                "src",
                "contracts.yaml",
                "domain-model.yaml",
                observe_domain_fn=_observed_domain,
            )
        self.assertTrue(report.has_drift)
        self.assertTrue(
            any("module_for_path" in m for m in report.signature_mismatches),
            report.signature_mismatches,
        )

    def test_aligned_repo_has_no_drift(self):
        with _tree(_base_files()):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertFalse(report.has_drift)
        self.assertEqual(report.missing_classes, ())
        self.assertEqual(report.field_mismatches, ())
        self.assertEqual(report.undeclared_contracts, ())

    def test_real_repo_is_aligned(self):
        # The committed repo: src + the two committed YAMLs must be ALIGNED.
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            report = compute_diff(
                "src",
                ".architecture/contracts.yaml",
                ".architecture/domain-model.yaml",
                observe_domain_fn=_observed_domain,
            )
        finally:
            os.chdir(cwd)
        self.assertFalse(report.has_drift, report)

    def test_renamed_field_is_drift(self):
        yaml_renamed = CONTRACTS_YAML.replace("path_glob: str", "path_glob_X: str")
        with _tree(_base_files({"contracts.yaml": yaml_renamed})):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertTrue(report.has_drift)
        self.assertTrue(report.field_mismatches)

    def test_changed_type_is_drift(self):
        yaml_typed = CONTRACTS_YAML.replace("name: str", "name: int")
        with _tree(_base_files({"contracts.yaml": yaml_typed})):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertTrue(report.has_drift)
        self.assertTrue(report.field_mismatches)

    def test_missing_class_is_drift(self):
        # YAML declares a contract the code does not define. The appended entry
        # aligns to the existing 2-space list indentation.
        yaml_extra = CONTRACTS_YAML + (
            "  - name: GhostContract\n"
            "    layer: contracts\n"
            "    module: src/contracts/ghost.py\n"
            '    crosses: "nowhere"\n'
            "    fields:\n"
            "      a: str\n"
        )
        with _tree(_base_files({"contracts.yaml": yaml_extra})):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertTrue(report.has_drift)
        self.assertIn("GhostContract", report.missing_classes)

    def test_undeclared_contract_in_code_is_drift(self):
        # A second contract class in code, absent from the YAML: the contract
        # seam must be complete, so this is drift.
        extra_src = CONTRACT_SRC + textwrap.dedent(
            """\

            @dataclass(frozen=True)
            class ExtraContract:
                value: int
            """
        )
        with _tree(_base_files({"src/contracts/x.py": extra_src})):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertTrue(report.has_drift)
        self.assertIn("ExtraContract", report.undeclared_contracts)

    def test_extra_observed_field_is_drift(self):
        # Code adds a field the YAML does not declare: strict, so drift.
        src_extra_field = CONTRACT_SRC + "    extra_field: int\n"
        with _tree(_base_files({"src/contracts/x.py": src_extra_field})):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertTrue(report.has_drift)
        self.assertTrue(report.field_mismatches)

    def test_empty_domain_is_aligned(self):
        with _tree(_base_files()):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertEqual(report.signature_mismatches, ())
        self.assertFalse(report.has_drift)

    def test_domain_signature_mismatch_is_drift(self):
        domain_src = textwrap.dedent(
            """\
            class RoutePolicy:
                def evaluate(self, route: str) -> int:
                    return 0
            """
        )
        domain_yaml = textwrap.dedent(
            """\
            domain_classes:
              - name: RoutePolicy
                layer: domain
                module: src/domain/route_policy.py
                responsibility: "score a route"
                invariants: []
                methods:
                  evaluate: "(self, route: str) -> str"
            """
        )
        files = _base_files(
            {
                "src/domain/__init__.py": "",
                "src/domain/route_policy.py": domain_src,
                "domain-model.yaml": domain_yaml,
            }
        )
        with _tree(files):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertTrue(report.has_drift)
        self.assertTrue(report.signature_mismatches)

    def test_domain_class_in_code_not_in_yaml_is_info_not_drift(self):
        # Domain YAML curates KEY classes only, so an observed domain class
        # absent from the YAML is info, never drift.
        domain_src = textwrap.dedent(
            """\
            class HelperPolicy:
                def helps(self) -> None:
                    return None
            """
        )
        files = _base_files(
            {
                "src/domain/__init__.py": "",
                "src/domain/helper.py": domain_src,
            }
        )
        with _tree(files):
            report = compute_diff("src", "contracts.yaml", "domain-model.yaml",
                                  observe_domain_fn=_observed_domain)
        self.assertFalse(report.has_drift)
        self.assertIn("HelperPolicy", report.info_only)


if __name__ == "__main__":
    unittest.main()
