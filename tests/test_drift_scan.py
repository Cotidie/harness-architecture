import contextlib
import os
import tempfile
import textwrap
import unittest

from scripts.drift_scan import compute_drift


@contextlib.contextmanager
def _tree(files):
    """Materialize {relpath: content} under a temp dir, yield its path, chdir
    into it so relative module globs resolve the way the harness runs them."""
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


BOUNDARIES = """\
modules:
  domain:
    path: "src/domain/**"
    may_depend_on: []
    must_not_depend_on: [adapters]
  adapters:
    path: "src/adapters/**"
    may_depend_on: [domain]
    must_not_depend_on: []
"""


class DriftScanTest(unittest.TestCase):
    def test_clean_tree_has_no_drift(self):
        with _tree(
            {
                "boundaries.yaml": BOUNDARIES,
                "src/domain/__init__.py": "",
                "src/domain/core.py": "x = 1\n",
                "src/adapters/__init__.py": "",
                "src/adapters/io.py": "import src.domain.core\n",
            }
        ):
            report = compute_drift("src", "boundaries.yaml")
        self.assertFalse(report.has_drift)
        self.assertEqual(report.undeclared_modules, ())
        self.assertEqual(report.undeclared_edges, ())

    def test_undeclared_module_is_flagged(self):
        with _tree(
            {
                "boundaries.yaml": BOUNDARIES,
                "src/domain/__init__.py": "",
                "src/domain/core.py": "x = 1\n",
                "src/rogue/__init__.py": "",
                "src/rogue/thing.py": "y = 2\n",
            }
        ):
            report = compute_drift("src", "boundaries.yaml")
        self.assertTrue(report.has_drift)
        self.assertIn("rogue", report.undeclared_modules)

    def test_undeclared_edge_is_flagged(self):
        # adapters -> domain is declared; domain importing adapters is NOT in
        # domain.may_depend_on but IS in must_not_depend_on, so it is forbidden
        # (linter's job), not undeclared. Add a third module to get a true
        # allowed-by-omission undeclared edge.
        boundaries = textwrap.dedent(
            """\
            modules:
              domain:
                path: "src/domain/**"
                may_depend_on: []
                must_not_depend_on: []
              shared:
                path: "src/shared/**"
                may_depend_on: []
                must_not_depend_on: []
            """
        )
        with _tree(
            {
                "boundaries.yaml": boundaries,
                "src/domain/__init__.py": "",
                # domain -> shared is neither allowed nor forbidden: undeclared.
                "src/domain/core.py": "import src.shared.util\n",
                "src/shared/__init__.py": "",
                "src/shared/util.py": "z = 3\n",
            }
        ):
            report = compute_drift("src", "boundaries.yaml")
        self.assertIn(("domain", "shared"), report.undeclared_edges)
        self.assertTrue(report.has_drift)

    def test_forbidden_edge_is_info_not_drift(self):
        # domain -> adapters is in must_not_depend_on: the linter catches it, so
        # the drift scan reports it as info and does NOT count it as drift.
        with _tree(
            {
                "boundaries.yaml": BOUNDARIES,
                "src/domain/__init__.py": "",
                "src/domain/core.py": "import src.adapters.io\n",
                "src/adapters/__init__.py": "",
                "src/adapters/io.py": "w = 4\n",
            }
        ):
            report = compute_drift("src", "boundaries.yaml")
        self.assertIn(("domain", "adapters"), report.forbidden_edges)
        self.assertEqual(report.undeclared_edges, ())
        self.assertFalse(report.has_drift)

    def test_unmaterialized_module_is_info_not_drift(self):
        with _tree(
            {
                "boundaries.yaml": BOUNDARIES,
                "src/domain/__init__.py": "",
                "src/domain/core.py": "x = 1\n",
            }
        ):
            report = compute_drift("src", "boundaries.yaml")
        self.assertIn("adapters", report.unmaterialized_modules)
        self.assertFalse(report.has_drift)


if __name__ == "__main__":
    unittest.main()
