import contextlib
import os
import tempfile
import unittest

from scripts.harness_paths import HarnessPathsError, resolve_paths


@contextlib.contextmanager
def _tree(files):
    with tempfile.TemporaryDirectory() as root:
        for relpath, content in files.items():
            full = os.path.join(root, relpath)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(content)
        yield root


class ResolvePathsTest(unittest.TestCase):
    def test_reads_source_root_and_builds_paths(self):
        with _tree({".architecture/profile.yaml": "source_root: app\n"}) as root:
            paths = resolve_paths(root)
        self.assertEqual(paths.source_dir, os.path.join(root, "app"))
        self.assertEqual(
            paths.boundaries, os.path.join(root, ".architecture", "boundaries.yaml")
        )
        self.assertEqual(
            paths.contracts, os.path.join(root, ".architecture", "contracts.yaml")
        )
        self.assertEqual(
            paths.domain_model,
            os.path.join(root, ".architecture", "domain-model.yaml"),
        )

    def test_missing_profile_raises(self):
        with _tree({"README.md": "# no profile\n"}) as root:
            with self.assertRaises(HarnessPathsError):
                resolve_paths(root)

    def test_profile_without_source_root_raises(self):
        with _tree({".architecture/profile.yaml": "label: x\nlanguage: python\n"}) as root:
            with self.assertRaises(HarnessPathsError):
                resolve_paths(root)


if __name__ == "__main__":
    unittest.main()
